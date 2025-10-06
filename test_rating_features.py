"""
Test script to verify rating and featured chef functionality
"""
from main import app, db
from models import Chef, Booking, Event, User
from datetime import datetime, timedelta

def test_features():
    with app.app_context():
        print("=" * 60)
        print("TESTING RATING & FEATURED CHEF SYSTEM")
        print("=" * 60)
        
        # Test 1: Check Chef model properties
        print("\n1. Testing Chef Model Properties...")
        chefs = Chef.query.filter_by(is_verified=True, is_approved=True).all()
        print(f"   Found {len(chefs)} verified/approved chefs")
        
        if chefs:
            chef = chefs[0]
            print(f"   ✓ Chef: {chef.name}")
            print(f"   ✓ Location property: {chef.location}")
            print(f"   ✓ Has ratings: {chef.has_ratings}")
            print(f"   ✓ Average rating: {chef.average_rating}")
            print(f"   ✓ Rating count: {chef.rating_count}")
            print(f"   ✓ Is featured: {chef.is_featured}")
            print(f"   ✓ Featured priority: {chef.featured_priority}")
        else:
            print("   ⚠ No chefs found in database")
        
        # Test 2: Check Featured Chefs Query
        print("\n2. Testing Featured Chefs Query...")
        from sqlalchemy import func
        featured_chefs = Chef.query.filter(
            Chef.is_verified.is_(True),
            Chef.is_approved.is_(True)
        ).order_by(
            Chef.is_featured.desc(),
            func.coalesce(Chef.featured_priority, 0).desc(),
            func.coalesce(Chef.rating_count, 0).desc(),
            func.coalesce(Chef.rating_total, 0).desc()
        ).limit(12).all()
        
        print(f"   ✓ Query executed successfully")
        print(f"   ✓ Found {len(featured_chefs)} chefs for spotlight")
        
        # Test 3: Check Booking Rating Fields
        print("\n3. Testing Booking Rating Fields...")
        bookings = Booking.query.all()
        print(f"   Found {len(bookings)} bookings")
        
        if bookings:
            booking = bookings[0]
            print(f"   ✓ Booking ID: {booking.id}")
            print(f"   ✓ Rating value: {booking.rating_value}")
            print(f"   ✓ Rating comment: {booking.rating_comment}")
            print(f"   ✓ Rating submitted at: {booking.rating_submitted_at}")
        else:
            print("   ⚠ No bookings found in database")
        
        # Test 4: Check for completed bookings that can be rated
        print("\n4. Testing Pending Reviews Logic...")
        confirmed_bookings = Booking.query.filter_by(status='confirmed').all()
        print(f"   Found {len(confirmed_bookings)} confirmed bookings")
        
        pending_reviews = []
        rated_bookings = []
        
        for booking in confirmed_bookings:
            if booking.event.event_date < datetime.utcnow():
                if booking.rating_value is None:
                    pending_reviews.append(booking)
                else:
                    rated_bookings.append(booking)
        
        print(f"   ✓ Pending reviews: {len(pending_reviews)}")
        print(f"   ✓ Already rated: {len(rated_bookings)}")
        
        # Test 5: Simulate rating calculation
        print("\n5. Testing Rating Calculation...")
        if chefs:
            chef = chefs[0]
            print(f"   Chef: {chef.name}")
            print(f"   Current rating_total: {chef.rating_total}")
            print(f"   Current rating_count: {chef.rating_count}")
            
            if chef.rating_count > 0:
                calculated_avg = chef.rating_total / chef.rating_count
                print(f"   ✓ Calculated average: {calculated_avg:.1f}")
                print(f"   ✓ Property average: {chef.average_rating}")
            else:
                print("   - No ratings yet for this chef")
        
        # Test 6: Check admin routes exist
        print("\n6. Testing Route Registration...")
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append(str(rule))
        
        required_routes = [
            '/booking/<int:booking_id>/rate',
            '/admin/featured-chefs',
            '/admin/chefs/<int:chef_id>/toggle-featured',
            '/admin/chefs/<int:chef_id>/set-priority'
        ]
        
        for route in required_routes:
            # Check if route pattern exists (may have different format)
            route_exists = any(route.replace('<int:', '<').replace('>', '') in r for r in routes)
            status = "✓" if route_exists else "✗"
            print(f"   {status} {route}")
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 60)
        print("\nNext Steps:")
        print("1. Start the Flask application")
        print("2. Login as a customer to test rating submission")
        print("3. Login as admin to manage featured chefs")
        print("4. Check the welcome page for featured chefs carousel")
        print("=" * 60)

if __name__ == '__main__':
    test_features()