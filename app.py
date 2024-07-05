from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_session import Session
from flask_cors import CORS
from datetime import timedelta

app = Flask(__name__)
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "https://agreeable-ground-084082a1e.5.azurestaticapps.net"}})
app.config['SECRET_KEY'] = 'my_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SESSION_TYPE'] = 'filesystem'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
sess = Session(app)


@app.route('/', methods=['GET'])
def Home():
    return "Hello world"

from api import *

if __name__ == '__main__':
    app.run(debug=True)