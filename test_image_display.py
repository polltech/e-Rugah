"""
Test chef image display
"""
from main import app
from models import db, Chef
import os

with app.app_context():
    chefs = Chef.query.filter_by(is_verified=True, is_approved=True).all()
    
    print(f"\n{'='*80}")
    print(f"CHEF IMAGE DISPLAY TEST")
    print(f"{'='*80}\n")
    
    for chef in chefs:
        print(f"Chef: {chef.name}")
        print(f"  Photo URL in DB: {chef.photo_url}")
        
        if chef.photo_url:
            # Remove leading slash and check if file exists
            file_path = chef.photo_url.lstrip('/')
            full_path = os.path.join('c:/Users/poll/e-Rugah', file_path)
            
            print(f"  Full file path: {full_path}")
            print(f"  File exists: {os.path.exists(full_path)}")
            
            if os.path.exists(full_path):
                file_size = os.path.getsize(full_path)
                print(f"  File size: {file_size:,} bytes ({file_size/1024:.2f} KB)")
            
            # Show what the HTML will render
            print(f"  HTML will use: <img src=\"{chef.photo_url}\" alt=\"{chef.name}\">")
        else:
            print(f"  No photo URL - will show emoji placeholder")
        
        print()
    
    print(f"Total verified & approved chefs: {len(chefs)}")