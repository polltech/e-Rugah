"""
Seed the custom dish database with sample dishes
Run this to populate dish.db with example data
"""
from main import app, db
from custom_dish_models import CustomDish, CustomIngredient, CustomDishIngredient

def seed_custom_dishes():
    """Add sample dishes to the custom dish database"""
    with app.app_context():
        # Check if already seeded
        if CustomDish.query.count() > 0:
            print("⚠️  Database already has dishes. Skipping seed.")
            print(f"   Current dishes: {CustomDish.query.count()}")
            return
        
        print("🌱 Seeding custom dish database...")
        
        # Dish 1: Pilau
        print("\n📝 Adding Pilau...")
        pilau = CustomDish(
            name="Pilau",
            base_servings=20,
            markup=55.0,
            description="Fragrant spiced rice with tender meat and aromatic spices"
        )
        db.session.add(pilau)
        db.session.commit()
        
        # Pilau ingredients
        ingredients_data = [
            ("Rice", "kg", 120.0, 4.0),
            ("Beef", "kg", 600.0, 3.0),
            ("Cooking Oil", "L", 250.0, 0.5),
            ("Onions", "kg", 80.0, 1.0),
            ("Pilau Masala", "pcs", 50.0, 2.0),
        ]
        
        for name, unit, price, qty in ingredients_data:
            ingredient = CustomIngredient.query.filter_by(name=name).first()
            if not ingredient:
                ingredient = CustomIngredient(name=name, unit=unit, unit_price=price)
                db.session.add(ingredient)
                db.session.commit()
            
            dish_ingredient = CustomDishIngredient(
                dish_id=pilau.id,
                ingredient_id=ingredient.id,
                quantity_for_base_servings=qty
            )
            db.session.add(dish_ingredient)
        
        db.session.commit()
        print("   ✅ Pilau added with 5 ingredients")
        
        # Dish 2: Chicken Curry
        print("\n📝 Adding Chicken Curry...")
        curry = CustomDish(
            name="Chicken Curry",
            base_servings=20,
            markup=50.0,
            description="Creamy chicken curry with aromatic spices"
        )
        db.session.add(curry)
        db.session.commit()
        
        # Chicken Curry ingredients
        curry_ingredients = [
            ("Chicken", "kg", 400.0, 4.0),
            ("Cooking Oil", "L", 250.0, 0.5),  # Reuse
            ("Onions", "kg", 80.0, 1.0),  # Reuse
            ("Tomatoes", "kg", 60.0, 2.0),
            ("Curry Powder", "kg", 300.0, 0.2),
            ("Coconut Milk", "L", 200.0, 1.0),
        ]
        
        for name, unit, price, qty in curry_ingredients:
            ingredient = CustomIngredient.query.filter_by(name=name).first()
            if not ingredient:
                ingredient = CustomIngredient(name=name, unit=unit, unit_price=price)
                db.session.add(ingredient)
                db.session.commit()
            
            dish_ingredient = CustomDishIngredient(
                dish_id=curry.id,
                ingredient_id=ingredient.id,
                quantity_for_base_servings=qty
            )
            db.session.add(dish_ingredient)
        
        db.session.commit()
        print("   ✅ Chicken Curry added with 6 ingredients")
        
        # Dish 3: Ugali
        print("\n📝 Adding Ugali...")
        ugali = CustomDish(
            name="Ugali",
            base_servings=20,
            markup=30.0,
            description="Traditional maize meal staple"
        )
        db.session.add(ugali)
        db.session.commit()
        
        # Ugali ingredients
        ugali_ingredients = [
            ("Maize Flour", "kg", 100.0, 5.0),
            ("Water", "L", 0.0, 10.0),
        ]
        
        for name, unit, price, qty in ugali_ingredients:
            ingredient = CustomIngredient.query.filter_by(name=name).first()
            if not ingredient:
                ingredient = CustomIngredient(name=name, unit=unit, unit_price=price)
                db.session.add(ingredient)
                db.session.commit()
            
            dish_ingredient = CustomDishIngredient(
                dish_id=ugali.id,
                ingredient_id=ingredient.id,
                quantity_for_base_servings=qty
            )
            db.session.add(dish_ingredient)
        
        db.session.commit()
        print("   ✅ Ugali added with 2 ingredients")
        
        # Summary
        print("\n" + "="*50)
        print("✅ Seeding complete!")
        print("="*50)
        print(f"📊 Total dishes: {CustomDish.query.count()}")
        print(f"📊 Total ingredients: {CustomIngredient.query.count()}")
        print("\n💡 Dishes added:")
        for dish in CustomDish.query.all():
            ingredient_count = CustomDishIngredient.query.filter_by(dish_id=dish.id).count()
            print(f"   - {dish.name} ({ingredient_count} ingredients, {dish.markup}% markup)")
        
        print("\n🎉 Customers can now search for these dishes!")
        print("   Try searching for: pilau, chicken curry, ugali")

if __name__ == '__main__':
    seed_custom_dishes()