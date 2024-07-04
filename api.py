from flask import request, jsonify, session, request
from app import app, db, bcrypt
from models import User, Transcription
from speech_recognition import UnknownValueError
import uuid
from googletrans import Translator
import speech_recognition as sr
from datetime import datetime
from app import db
from models import Transcription, User
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from collections import Counter
import re









@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    user = User(username=data['username'], email=data['email'], password=hashed_password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    if user and bcrypt.check_password_hash(user.password, data['password']):
        session['user_id'] = user.id
        return jsonify({'message': 'Login successful'}), 200
    return jsonify({'message': 'Login failed'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'}), 200




@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    file = request.files['file']
    recognizer = sr.Recognizer()
    audio = sr.AudioFile(file)
    
    try:
        with audio as source:
            audio_data = recognizer.record(source)
            original_text = recognizer.recognize_google(audio_data) 
    except UnknownValueError:
        return jsonify({'error': 'Speech could not be recognized'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    translator = Translator()

    try:
        translated_text = translator.translate(original_text, dest='en').text
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    transcription = Transcription(
        user_id=session['user_id'],
        original_text=original_text,
        translated_text=translated_text,
        timestamp=datetime.utcnow()
    )
    
    db.session.add(transcription)
    db.session.commit()

    return jsonify({
        'original_text': original_text,
        'translated_text': translated_text
    }), 200



@app.route('/history', methods=['GET'])
def history():
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    transcriptions = Transcription.query.filter_by(user_id=session['user_id']).all()
    history = [{
        'original_text': transcription.original_text,
        'translated_text': transcription.translated_text,
        'timestamp': transcription.timestamp
    } for transcription in transcriptions]

    return jsonify({'history': history}), 200



@app.route('/word_frequencies', methods=['GET'])
def word_frequencies():
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    current_user_id = session['user_id']
    
    user_transcriptions = Transcription.query.filter_by(user_id=current_user_id).all()
    all_transcriptions = Transcription.query.all()

    def count_words(transcriptions):
        word_counter = Counter()
        for transcription in transcriptions:
            words = re.findall(r'\b\w+\b', transcription.translated_text.lower())
            word_counter.update(words)
        return word_counter

    def get_top_words(word_counter, top_n=10):
        most_common_words = word_counter.most_common(top_n)
        sorted_words = {word: count for word, count in sorted(most_common_words, key=lambda x: x[1], reverse=True)}
        return sorted_words

    user_word_count = count_words(user_transcriptions)
    all_word_count = count_words(all_transcriptions)

    top_user_words = get_top_words(user_word_count)
    top_all_words = get_top_words(all_word_count)

    return jsonify({
        'user_word_count': top_user_words,
        'all_word_count': top_all_words
    }), 200




@app.route('/unique_phrases', methods=['GET'])
def unique_phrases():
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    current_user_id = session['user_id']
    
    user_transcriptions = Transcription.query.filter_by(user_id=current_user_id).all()

    def count_phrases(transcriptions, min_length=2):
        phrase_counter = Counter()
        for transcription in transcriptions:
            words = re.findall(r'\b\w+\b', transcription.translated_text.lower())
            for i in range(len(words) - min_length + 1):
                for j in range(i + min_length, len(words) + 1):
                    phrase = ' '.join(words[i:j])
                    phrase_counter[phrase] += 1
        return phrase_counter

    def get_top_phrases(phrase_counter, top_n=3):
        most_common_phrases = phrase_counter.most_common(top_n)
        sorted_phrases = {phrase: count for phrase, count in sorted(most_common_phrases, key=lambda x: x[1], reverse=True)}
        return sorted_phrases

    user_phrase_count = count_phrases(user_transcriptions)

    top_user_phrases = get_top_phrases(user_phrase_count)

    return jsonify({
        'user_unique_phrases': top_user_phrases
    }), 200


@app.route('/similar_users', methods=['GET'])
def similar_users():
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    current_user_id = session['user_id']

    user_transcriptions = Transcription.query.filter_by(user_id=current_user_id).all()
    user_texts = [transcription.translated_text for transcription in user_transcriptions]

    user_combined_text = ' '.join(user_texts)

    all_users = User.query.all()
    all_user_texts = []
    user_ids = []
    user_map = {}  

    for user in all_users:
        if user.id != current_user_id:
            transcriptions = Transcription.query.filter_by(user_id=user.id).all()
            combined_text = ' '.join([transcription.translated_text for transcription in transcriptions])
            if combined_text:
                all_user_texts.append(combined_text)
                user_ids.append(user.id)
                user_map[user.id] = user.username

    all_user_texts.append(user_combined_text)
    user_ids.append(current_user_id)

    vectorizer = TfidfVectorizer().fit_transform(all_user_texts)
    vectors = vectorizer.toarray()

    cosine_similarities = cosine_similarity(vectors)

    current_user_index = len(user_ids) - 1
    current_user_similarities = cosine_similarities[current_user_index]

    similarities = [(user_ids[i], current_user_similarities[i]) for i in range(len(user_ids)) if user_ids[i] != current_user_id]
    most_similar_users = sorted(similarities, key=lambda x: x[1], reverse=True)[:5]  # Get top 5 most similar users

    response = [{'username': user_map[user_id], 'similarity_score': score} for user_id, score in most_similar_users]

    return jsonify({'most_similar_users': response}), 200



@app.route('/check-auth', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        return jsonify({'isAuthenticated': True}), 200
    else:
        return jsonify({'isAuthenticated': False}), 401
