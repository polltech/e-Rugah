"""
Migration script to fix chef photo files and URLs.
This script:
1. Renames files with spaces/special chars to secure filenames
2. Updates database photo_url to match the new filenames
3. Ensures all photo_url entries have the /static/ prefix
"""
import sys
import os
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erugah.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Chef(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    photo_url = db.Column(db.String(200))


def fix_chef_photos():
    """Fix photo files and URLs for all chefs"""
    with app.app_context():
        chefs = Chef.query.all()
        fixed_count = 0
        renamed_count = 0
        
        print(f"Found {len(chefs)} chefs in database")
        print("-" * 70)
        
        chefs_dir = os.path.join('static', 'images', 'chefs')
        
        for chef in chefs:
            if chef.photo_url:
                # Extract filename from photo_url
                if chef.photo_url.startswith('/static/'):
                    filename = chef.photo_url.replace('/static/images/chefs/', '')
                elif chef.photo_url.startswith('images/'):
                    filename = chef.photo_url.replace('images/chefs/', '')
                else:
                    filename = os.path.basename(chef.photo_url)
                
                old_file_path = os.path.join(chefs_dir, filename)
                
                # Check if file exists
                if os.path.exists(old_file_path):
                    # Generate secure filename
                    secure_name = secure_filename(filename)
                    new_file_path = os.path.join(chefs_dir, secure_name)
                    
                    # If filename needs to be changed
                    if filename != secure_name:
                        # Rename the file
                        if os.path.exists(new_file_path):
                            print(f"⚠ Chef {chef.id} ({chef.name}): Target file already exists")
                            print(f"  Skipping: {secure_name}")
                        else:
                            shutil.move(old_file_path, new_file_path)
                            renamed_count += 1
                            print(f"✓ Renamed file for Chef {chef.id} ({chef.name}):")
                            print(f"  Old: {filename}")
                            print(f"  New: {secure_name}")
                        
                        # Update database
                        old_url = chef.photo_url
                        chef.photo_url = f"/static/images/chefs/{secure_name}"
                        fixed_count += 1
                        print(f"  Updated URL: {chef.photo_url}")
                    else:
                        # Just ensure URL has correct prefix
                        if not chef.photo_url.startswith('/static/'):
                            old_url = chef.photo_url
                            chef.photo_url = f"/static/images/chefs/{secure_name}"
                            fixed_count += 1
                            print(f"✓ Fixed URL for Chef {chef.id} ({chef.name}):")
                            print(f"  Old: {old_url}")
                            print(f"  New: {chef.photo_url}")
                        else:
                            print(f"✓ Chef {chef.id} ({chef.name}): Already correct")
                else:
                    print(f"⚠ Chef {chef.id} ({chef.name}): File not found - {old_file_path}")
            else:
                print(f"○ Chef {chef.id} ({chef.name}): No photo URL")
        
        if fixed_count > 0 or renamed_count > 0:
            db.session.commit()
            print("-" * 70)
            print(f"✓ Renamed {renamed_count} files")
            print(f"✓ Updated {fixed_count} database records")
        else:
            print("-" * 70)
            print("✓ All chef photos are already correct")
        
        return fixed_count, renamed_count


if __name__ == '__main__':
    print("Starting chef photo files and URLs migration...")
    print("=" * 70)
    fixed, renamed = fix_chef_photos()
    print("=" * 70)
    print(f"Migration complete! Renamed {renamed} files, updated {fixed} records.")