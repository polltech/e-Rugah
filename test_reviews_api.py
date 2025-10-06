"""
Quick test script to verify the reviews API is working
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import db, Review

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erugah.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    try:
        # Query all approved reviews
        reviews = Review.query.filter_by(is_approved=True).all()
        
        print("="*60)
        print(f"FOUND {len(reviews)} APPROVED REVIEWS")
        print("="*60)
        
        for i, review in enumerate(reviews, 1):
            print(f"\n{i}. {review.customer_name} - {review.event_type}")
            print(f"   Rating: {'⭐' * review.rating}")
            print(f"   Review: {review.review_text[:80]}...")
            print(f"   Approved: {review.is_approved}")
            print(f"   Created: {review.created_at}")
        
        print("\n" + "="*60)
        print("✓ Reviews API data is ready!")
        print("="*60)
        
        # Test JSON serialization
        print("\nTesting JSON serialization...")
        review_data = [{
            'id': r.id,
            'customer_name': r.customer_name,
            'event_type': r.event_type,
            'rating': r.rating,
            'review_text': r.review_text,
            'created_at': r.created_at.strftime('%Y-%m-%d')
        } for r in reviews]
        
        print(f"✓ Successfully serialized {len(review_data)} reviews to JSON format")
        print("\nSample JSON output:")
        import json
        print(json.dumps(review_data[0], indent=2))
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()