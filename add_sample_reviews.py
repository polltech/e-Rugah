"""
Script to add sample reviews to the database
Run this after running migrate_add_reviews.py
"""
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import random

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

# Sample review data
sample_reviews = [
    {
        "customer_name": "Sarah & Michael Johnson",
        "event_type": "Wedding",
        "rating": 5,
        "review_text": "e-Rugah made our wedding absolutely magical! The decor was stunning, the food was delicious, and the staff was incredibly professional. Our guests are still talking about how beautiful everything was. Thank you for making our special day perfect!",
        "days_ago": 5
    },
    {
        "customer_name": "David Kimani",
        "event_type": "Corporate Event",
        "rating": 5,
        "review_text": "We hosted our annual company gala at e-Rugah and it exceeded all expectations. The venue was elegant, the catering was top-notch, and the event coordination was flawless. Highly recommend for corporate events!",
        "days_ago": 12
    },
    {
        "customer_name": "Grace Wanjiru",
        "event_type": "Birthday Party",
        "rating": 5,
        "review_text": "My 40th birthday party was absolutely incredible! The team at e-Rugah handled everything perfectly. The decorations were beautiful, the entertainment was fantastic, and all my guests had an amazing time. Worth every penny!",
        "days_ago": 8
    },
    {
        "customer_name": "James & Emily Ochieng",
        "event_type": "Wedding",
        "rating": 5,
        "review_text": "From the initial consultation to the last dance, e-Rugah was phenomenal. They understood our vision and brought it to life beautifully. The attention to detail was impressive, and the service was impeccable. Our dream wedding came true!",
        "days_ago": 20
    },
    {
        "customer_name": "Patricia Muthoni",
        "event_type": "Graduation Party",
        "rating": 5,
        "review_text": "What an amazing celebration! e-Rugah organized my daughter's graduation party and it was perfect. The venue setup was elegant, the food was delicious, and the staff was so helpful. Everyone had a wonderful time!",
        "days_ago": 15
    },
    {
        "customer_name": "Robert Kamau",
        "event_type": "Corporate Event",
        "rating": 4,
        "review_text": "Great venue for our product launch event. The facilities were modern and well-maintained. The catering service was excellent and the technical support was very helpful. Would definitely use again for future events.",
        "days_ago": 30
    },
    {
        "customer_name": "Linda & Peter Njoroge",
        "event_type": "Wedding",
        "rating": 5,
        "review_text": "e-Rugah turned our wedding into a fairytale! The garden setting was breathtaking, the coordination was seamless, and every detail was perfect. Our families and friends keep saying it was the best wedding they've ever attended. Thank you!",
        "days_ago": 45
    },
    {
        "customer_name": "Catherine Akinyi",
        "event_type": "Baby Shower",
        "rating": 5,
        "review_text": "My baby shower was absolutely beautiful! The decorations were adorable, the food was amazing, and the staff made sure everything ran smoothly. All my guests were impressed. Thank you e-Rugah for making this day so special!",
        "days_ago": 10
    },
    {
        "customer_name": "John Mwangi",
        "event_type": "Anniversary",
        "rating": 5,
        "review_text": "Celebrated our 25th wedding anniversary at e-Rugah and it was unforgettable. The romantic ambiance, excellent service, and delicious food made it a night to remember. Highly recommend for special celebrations!",
        "days_ago": 18
    },
    {
        "customer_name": "Mary Wangari",
        "event_type": "Bridal Shower",
        "rating": 5,
        "review_text": "The bridal shower was perfect in every way! The venue was beautifully decorated, the food was delicious, and the staff was attentive and friendly. My sister was so happy, and all the guests had a great time. Thank you!",
        "days_ago": 7
    },
    {
        "customer_name": "Thomas & Jane Otieno",
        "event_type": "Wedding",
        "rating": 5,
        "review_text": "Our wedding at e-Rugah was beyond our wildest dreams! The team was professional, creative, and made sure every detail was perfect. The venue was stunning, the food was exceptional, and the service was outstanding. Couldn't have asked for more!",
        "days_ago": 60
    },
    {
        "customer_name": "Susan Chebet",
        "event_type": "Retirement Party",
        "rating": 5,
        "review_text": "My husband's retirement party was a huge success thanks to e-Rugah! The venue was perfect, the catering was excellent, and the staff went above and beyond to make sure everything was perfect. All our guests had a wonderful time!",
        "days_ago": 25
    },
    {
        "customer_name": "Daniel Kipchoge",
        "event_type": "Corporate Event",
        "rating": 5,
        "review_text": "Hosted our team building event at e-Rugah and it was fantastic! The facilities were great, the food was delicious, and the staff was very accommodating. Perfect venue for corporate gatherings. Will definitely be back!",
        "days_ago": 14
    },
    {
        "customer_name": "Rachel Nyambura",
        "event_type": "Birthday Party",
        "rating": 5,
        "review_text": "My son's 21st birthday party was absolutely amazing! The decorations were on point, the DJ was great, and the food was delicious. The staff made sure everything ran smoothly. Thank you e-Rugah for an unforgettable celebration!",
        "days_ago": 22
    },
    {
        "customer_name": "George & Anne Mutua",
        "event_type": "Wedding",
        "rating": 5,
        "review_text": "e-Rugah made our wedding day absolutely perfect! From the beautiful decorations to the amazing food and impeccable service, everything was flawless. Our guests are still raving about it. Thank you for creating such wonderful memories!",
        "days_ago": 35
    }
]

def add_sample_reviews():
    with app.app_context():
        try:
            # Check if reviews already exist
            existing_count = Review.query.count()
            if existing_count > 0:
                print(f"⚠ Warning: Database already contains {existing_count} review(s)")
                response = input("Do you want to add sample reviews anyway? (yes/no): ")
                if response.lower() not in ['yes', 'y']:
                    print("Operation cancelled.")
                    return
            
            print(f"\nAdding {len(sample_reviews)} sample reviews...")
            
            added_count = 0
            for review_data in sample_reviews:
                # Calculate created_at date
                created_at = datetime.utcnow() - timedelta(days=review_data['days_ago'])
                
                review = Review(
                    customer_name=review_data['customer_name'],
                    event_type=review_data['event_type'],
                    rating=review_data['rating'],
                    review_text=review_data['review_text'],
                    is_approved=True,  # Approve all sample reviews
                    created_at=created_at
                )
                
                db.session.add(review)
                added_count += 1
                print(f"  ✓ Added review from {review_data['customer_name']} ({review_data['event_type']}, {review_data['rating']} stars)")
            
            db.session.commit()
            print(f"\n✓ Successfully added {added_count} sample reviews!")
            
            # Show summary
            total_reviews = Review.query.count()
            approved_reviews = Review.query.filter_by(is_approved=True).count()
            pending_reviews = Review.query.filter_by(is_approved=False).count()
            
            print("\n" + "="*50)
            print("DATABASE SUMMARY:")
            print("="*50)
            print(f"Total reviews: {total_reviews}")
            print(f"Approved reviews: {approved_reviews}")
            print(f"Pending reviews: {pending_reviews}")
            
            # Show rating distribution
            print("\nRating Distribution:")
            for rating in range(5, 0, -1):
                count = Review.query.filter_by(rating=rating).count()
                stars = "⭐" * rating
                print(f"  {stars} ({rating}): {count} reviews")
            
            # Show event type distribution
            print("\nEvent Type Distribution:")
            event_types = db.session.query(Review.event_type, db.func.count(Review.id)).group_by(Review.event_type).all()
            for event_type, count in event_types:
                print(f"  {event_type}: {count} reviews")
            
        except Exception as e:
            print(f"✗ Error adding sample reviews: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    print("="*50)
    print("SAMPLE REVIEWS GENERATOR")
    print("="*50)
    print(f"Database path: {os.path.abspath('erugah.db')}")
    add_sample_reviews()
    print("\n" + "="*50)
    print("Operation completed!")
    print("="*50)