"""Migration to add chef spotlight and rating enhancements."""
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
    is_featured = db.Column(db.Boolean, default=False)
    featured_priority = db.Column(db.Integer, default=100)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating_comment = db.Column(db.Text)


def migrate():
    with app.app_context():
        conn = db.engine.connect()
        inspector = db.inspect(conn)

        chef_columns = {c['name'] for c in inspector.get_columns('chef')}
        if 'is_featured' not in chef_columns:
            conn.execute(db.text('ALTER TABLE chef ADD COLUMN is_featured BOOLEAN DEFAULT 0'))
        if 'featured_priority' not in chef_columns:
            conn.execute(db.text('ALTER TABLE chef ADD COLUMN featured_priority INTEGER DEFAULT 100'))

        booking_columns = {c['name'] for c in inspector.get_columns('booking')}
        if 'rating_comment' not in booking_columns:
            conn.execute(db.text('ALTER TABLE booking ADD COLUMN rating_comment TEXT'))

        conn.close()
        print('✓ Migration completed: spotlight and rating fields')


if __name__ == '__main__':
    migrate()