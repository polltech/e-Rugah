from main import app, db
from models import Dish, Ingredient, DishIngredient

def seed_database():
    with app.app_context():
        # Create all tables
        db.create_all()

        # Sample ingredients
        ingredients_data = [
            {"name": "Beef", "unit": "kg", "unit_price": 800.0},
            {"name": "Onions", "unit": "kg", "unit_price": 50.0},
            {"name": "Tomatoes", "unit": "kg", "unit_price": 60.0},
            {"name": "Potatoes", "unit": "kg", "unit_price": 40.0},
            {"name": "Carrots", "unit": "kg", "unit_price": 70.0},
            {"name": "Chicken", "unit": "kg", "unit_price": 350.0},
            {"name": "Rice", "unit": "kg", "unit_price": 120.0},
            {"name": "Coconut Milk", "unit": "l", "unit_price": 150.0},
            {"name": "Chapati Flour", "unit": "kg", "unit_price": 90.0},
            {"name": "Cooking Oil", "unit": "l", "unit_price": 200.0},
            {"name": "Maize Flour", "unit": "kg", "unit_price": 80.0},
            {"name": "Bananas", "unit": "kg", "unit_price": 100.0},
            {"name": "Spices", "unit": "kg", "unit_price": 300.0},
        ]

        ingredients = {}
        for data in ingredients_data:
            ingredient = Ingredient.query.filter_by(name=data["name"]).first()
            if not ingredient:
                ingredient = Ingredient(**data)
                db.session.add(ingredient)
                db.session.commit()
            ingredients[data["name"]] = ingredient

        # Sample dishes
        dishes_data = [
            {
                "name": "Beef Stew",
                "base_servings": 4,
                "markup": 50.0,
                "description": "Traditional Kenyan beef stew with vegetables",
                "ingredients": [
                    {"name": "Beef", "quantity": 1.0},
                    {"name": "Onions", "quantity": 0.5},
                    {"name": "Tomatoes", "quantity": 0.3},
                    {"name": "Potatoes", "quantity": 0.8},
                    {"name": "Carrots", "quantity": 0.4},
                    {"name": "Cooking Oil", "quantity": 0.1},
                ]
            },
            {
                "name": "Chicken Curry",
                "base_servings": 4,
                "markup": 45.0,
                "description": "Spicy chicken curry with rice",
                "ingredients": [
                    {"name": "Chicken", "quantity": 1.2},
                    {"name": "Onions", "quantity": 0.4},
                    {"name": "Tomatoes", "quantity": 0.3},
                    {"name": "Rice", "quantity": 0.6},
                    {"name": "Coconut Milk", "quantity": 0.4},
                    {"name": "Cooking Oil", "quantity": 0.1},
                ]
            },
            {
                "name": "Chapati",
                "base_servings": 6,
                "markup": 40.0,
                "description": "Soft and fluffy Kenyan chapatis",
                "ingredients": [
                    {"name": "Chapati Flour", "quantity": 1.0},
                    {"name": "Cooking Oil", "quantity": 0.2},
                ]
            },
            {
                "name": "Ugali",
                "base_servings": 4,
                "markup": 30.0,
                "description": "Staple Kenyan maize meal porridge",
                "ingredients": [
                    {"name": "Maize Flour", "quantity": 1.0},
                ]
            },
            {
                "name": "Matoke",
                "base_servings": 4,
                "markup": 35.0,
                "description": "Stewed green bananas with vegetables",
                "ingredients": [
                    {"name": "Bananas", "quantity": 2.0},
                    {"name": "Onions", "quantity": 0.3},
                    {"name": "Tomatoes", "quantity": 0.2},
                    {"name": "Cooking Oil", "quantity": 0.1},
                ]
            },
            {
                "name": "Pilau",
                "base_servings": 4,
                "markup": 55.0,
                "description": "Fragrant spiced rice with meat",
                "ingredients": [
                    {"name": "Rice", "quantity": 0.8},
                    {"name": "Beef", "quantity": 0.8},
                    {"name": "Onions", "quantity": 0.4},
                    {"name": "Spices", "quantity": 0.1},
                    {"name": "Cooking Oil", "quantity": 0.1},
                ]
            }
        ]

        for dish_data in dishes_data:
            dish = Dish(
                name=dish_data["name"],
                base_servings=dish_data["base_servings"],
                markup=dish_data["markup"],
                description=dish_data["description"]
            )
            db.session.add(dish)
            db.session.commit()

            for ing_data in dish_data["ingredients"]:
                ingredient = ingredients[ing_data["name"]]
                dish_ingredient = DishIngredient(
                    dish_id=dish.id,
                    ingredient_id=ingredient.id,
                    quantity_for_base_servings=ing_data["quantity"]
                )
                db.session.add(dish_ingredient)

            db.session.commit()

        print("Database seeded successfully!")

if __name__ == "__main__":
    seed_database()