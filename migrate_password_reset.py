"""
Migration script to add PasswordResetCode table to the database
Run this script once to update your database schema
"""

from main import app
from models import db, PasswordResetCode

def migrate():
    with app.app_context():
        print("Creating PasswordResetCode table...")
        db.create_all()
        print("✓ Migration completed successfully!")
        print("The password reset feature is now ready to use.")

if __name__ == '__main__':
    migrate()