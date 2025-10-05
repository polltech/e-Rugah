"""
Initialize the custom dish database (dish.db)
Run this script once to create the database tables
"""
from main import app, db
from custom_dish_models import CustomDish, CustomIngredient, CustomDishIngredient

def init_custom_dish_database():
    """Create all tables in the custom dish database"""
    with app.app_context():
        # Create all tables (including bind_key tables)
        db.create_all()
        print("✅ Custom dish database (dish.db) initialized successfully!")
        
        # Check if there's any data
        dish_count = CustomDish.query.count()
        ingredient_count = CustomIngredient.query.count()
        
        print(f"📊 Current database status:")
        print(f"   - Dishes: {dish_count}")
        print(f"   - Ingredients: {ingredient_count}")
        
        if dish_count == 0:
            print("\n💡 Database is empty. You can now add dishes via the admin panel:")
            print("   1. Login as admin")
            print("   2. Go to Admin Dashboard")
            print("   3. Click 'Custom Dish DB' button")
            print("   4. Add your first dish!")

if __name__ == '__main__':
    init_custom_dish_database()