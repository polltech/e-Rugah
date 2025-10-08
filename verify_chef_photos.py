"""Verify chef photo URLs in database"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erugah.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Chef(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    photo_url = db.Column(db.String(200))

with app.app_context():
    chefs = Chef.query.all()
    print("Current chef photo URLs:")
    print("-" * 70)
    for chef in chefs:
        print(f"Chef {chef.id}: {chef.name}")
        print(f"  Photo URL: {chef.photo_url}")
        if chef.photo_url:
            # Check if file exists
            if chef.photo_url.startswith('/static/'):
                file_path = chef.photo_url.replace('/static/', 'static/')
                exists = os.path.exists(file_path)
                print(f"  File exists: {exists}")
                if not exists:
                    print(f"  Expected path: {file_path}")
        print()