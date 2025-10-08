"""
Migration script to fix chef photo URLs in the database.
This script adds the /static/ prefix to photo_url fields that are missing it.
"""
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


def fix_chef_photo_urls():
    """Fix photo URLs for all chefs in the database"""
    with app.app_context():
        # Get all chefs
        chefs = Chef.query.all()
        fixed_count = 0
        
        print(f"Found {len(chefs)} chefs in database")
        print("-" * 50)
        
        for chef in chefs:
            if chef.photo_url:
                # Check if photo_url is missing the /static/ prefix
                if not chef.photo_url.startswith('/static/') and not chef.photo_url.startswith('http'):
                    old_url = chef.photo_url
                    
                    # Add /static/ prefix if it starts with images/
                    if chef.photo_url.startswith('images/'):
                        chef.photo_url = f"/static/{chef.photo_url}"
                        fixed_count += 1
                        print(f"✓ Fixed Chef {chef.id} ({chef.name}):")
                        print(f"  Old: {old_url}")
                        print(f"  New: {chef.photo_url}")
                    # If it doesn't start with images/, assume it needs full path
                    elif not chef.photo_url.startswith('/'):
                        chef.photo_url = f"/static/images/chefs/{chef.photo_url}"
                        fixed_count += 1
                        print(f"✓ Fixed Chef {chef.id} ({chef.name}):")
                        print(f"  Old: {old_url}")
                        print(f"  New: {chef.photo_url}")
                else:
                    print(f"✓ Chef {chef.id} ({chef.name}): Already correct")
            else:
                print(f"○ Chef {chef.id} ({chef.name}): No photo URL")
        
        if fixed_count > 0:
            db.session.commit()
            print("-" * 50)
            print(f"✓ Successfully fixed {fixed_count} chef photo URLs")
        else:
            print("-" * 50)
            print("✓ All chef photo URLs are already correct")
        
        return fixed_count


if __name__ == '__main__':
    print("Starting chef photo URL migration...")
    print("=" * 50)
    fixed = fix_chef_photo_urls()
    print("=" * 50)
    print(f"Migration complete! Fixed {fixed} records.")