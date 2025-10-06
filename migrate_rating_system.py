"""
Database migration script to add rating and featured chef columns
"""
from main import app, db
from models import Chef, Booking

def migrate_database():
    with app.app_context():
        print("Starting database migration...")
        
        # Get database connection
        connection = db.engine.connect()
        
        try:
            # Add columns to Chef table
            print("\n1. Adding rating columns to Chef table...")
            
            # Check if columns already exist
            result = connection.execute(db.text("PRAGMA table_info(chef)"))
            existing_columns = [row[1] for row in result]
            
            if 'rating_total' not in existing_columns:
                connection.execute(db.text("ALTER TABLE chef ADD COLUMN rating_total INTEGER DEFAULT 0"))
                print("   ✓ Added rating_total column")
            else:
                print("   - rating_total column already exists")
            
            if 'rating_count' not in existing_columns:
                connection.execute(db.text("ALTER TABLE chef ADD COLUMN rating_count INTEGER DEFAULT 0"))
                print("   ✓ Added rating_count column")
            else:
                print("   - rating_count column already exists")
            
            if 'is_featured' not in existing_columns:
                connection.execute(db.text("ALTER TABLE chef ADD COLUMN is_featured BOOLEAN DEFAULT 0"))
                print("   ✓ Added is_featured column")
            else:
                print("   - is_featured column already exists")
            
            if 'featured_priority' not in existing_columns:
                connection.execute(db.text("ALTER TABLE chef ADD COLUMN featured_priority INTEGER DEFAULT 100"))
                print("   ✓ Added featured_priority column")
            else:
                print("   - featured_priority column already exists")
            
            # Add columns to Booking table
            print("\n2. Adding rating columns to Booking table...")
            
            result = connection.execute(db.text("PRAGMA table_info(booking)"))
            existing_columns = [row[1] for row in result]
            
            if 'rating_value' not in existing_columns:
                connection.execute(db.text("ALTER TABLE booking ADD COLUMN rating_value INTEGER"))
                print("   ✓ Added rating_value column")
            else:
                print("   - rating_value column already exists")
            
            if 'rating_comment' not in existing_columns:
                connection.execute(db.text("ALTER TABLE booking ADD COLUMN rating_comment TEXT"))
                print("   ✓ Added rating_comment column")
            else:
                print("   - rating_comment column already exists")
            
            if 'rating_submitted_at' not in existing_columns:
                connection.execute(db.text("ALTER TABLE booking ADD COLUMN rating_submitted_at DATETIME"))
                print("   ✓ Added rating_submitted_at column")
            else:
                print("   - rating_submitted_at column already exists")
            
            connection.commit()
            print("\n✅ Database migration completed successfully!")
            
            # Show current chef table structure
            print("\n3. Current Chef table structure:")
            result = connection.execute(db.text("PRAGMA table_info(chef)"))
            for row in result:
                print(f"   - {row[1]} ({row[2]})")
            
            # Show current booking table structure
            print("\n4. Current Booking table structure:")
            result = connection.execute(db.text("PRAGMA table_info(booking)"))
            for row in result:
                print(f"   - {row[1]} ({row[2]})")
            
        except Exception as e:
            connection.rollback()
            print(f"\n❌ Error during migration: {str(e)}")
            raise
        finally:
            connection.close()

if __name__ == '__main__':
    migrate_database()