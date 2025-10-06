"""
Migration script to add rating fields to Chef and Booking tables.
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erugah.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Chef(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating_total = db.Column(db.Integer, default=0)
    rating_count = db.Column(db.Integer, default=0)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating_value = db.Column(db.Integer)
    rating_submitted_at = db.Column(db.DateTime)


def migrate():
    with app.app_context():
        conn = db.engine.connect()

        inspector = db.inspect(conn)

        columns = {c['name'] for c in inspector.get_columns('chef')}
        if 'rating_total' not in columns:
            conn.execute(db.text('ALTER TABLE chef ADD COLUMN rating_total INTEGER DEFAULT 0'))
        if 'rating_count' not in columns:
            conn.execute(db.text('ALTER TABLE chef ADD COLUMN rating_count INTEGER DEFAULT 0'))

        columns = {c['name'] for c in inspector.get_columns('booking')}
        if 'rating_value' not in columns:
            conn.execute(db.text('ALTER TABLE booking ADD COLUMN rating_value INTEGER'))
        if 'rating_submitted_at' not in columns:
            conn.execute(db.text('ALTER TABLE booking ADD COLUMN rating_submitted_at DATETIME'))

        conn.close()
        print('✓ Migration completed: chef.rating_total, chef.rating_count, booking.rating_value, booking.rating_submitted_at')


if __name__ == '__main__':
    migrate()