"""
Check chef photo URLs in database
"""
from main import app
from models import db, Chef

with app.app_context():
    chefs = Chef.query.all()
    
    print(f"\n{'='*80}")
    print(f"CHEF PHOTO URL CHECK")
    print(f"{'='*80}\n")
    
    for chef in chefs:
        print(f"Chef: {chef.name}")
        print(f"  Email: {chef.user.email}")
        print(f"  Photo URL: {chef.photo_url}")
        print(f"  Is Verified: {chef.is_verified}")
        print(f"  Is Approved: {chef.is_approved}")
        print(f"  Is Featured: {chef.is_featured}")
        print()
    
    print(f"Total chefs: {len(chefs)}")