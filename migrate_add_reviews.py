"""
Migration script to add the Review table to the database
Run this script to create the Review table in your database.
"""
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erugah.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Define Review model
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def migrate():
    with app.app_context():
        try:
            # Create the Review table
            db.create_all()
            print("✓ Review table created successfully!")
            
            # Verify the table was created
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'review' in tables:
                print("✓ Verified: 'review' table exists in database")
                
                # Show table columns
                columns = inspector.get_columns('review')
                print("\nTable columns:")
                for col in columns:
                    print(f"  - {col['name']}: {col['type']}")
            else:
                print("✗ Error: 'review' table was not created")
                
        except Exception as e:
            print(f"✗ Error during migration: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    print("Starting migration: Adding Review table...")
    print(f"Database path: {os.path.abspath('erugah.db')}")
    migrate()
    print("\nMigration completed!")