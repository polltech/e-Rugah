"""
Database Migration Script
Adds email_verified and sms_verified fields to User table
"""

from main import app, db
from models import User

def migrate_database():
    with app.app_context():
        try:
            # Check if columns already exist
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('user')]
            
            if 'email_verified' in columns and 'sms_verified' in columns:
                print("✅ Verification fields already exist in database")
                return
            
            print("🔄 Adding verification fields to User table...")
            
            # Add columns using raw SQL
            with db.engine.connect() as conn:
                if 'email_verified' not in columns:
                    conn.execute(db.text("ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0"))
                    print("✅ Added email_verified column")
                
                if 'sms_verified' not in columns:
                    conn.execute(db.text("ALTER TABLE user ADD COLUMN sms_verified BOOLEAN DEFAULT 0"))
                    print("✅ Added sms_verified column")
                
                conn.commit()
            
            print("✅ Migration completed successfully!")
            print("\nNext steps:")
            print("1. Restart your Flask application")
            print("2. Test the new verification flow")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    migrate_database()