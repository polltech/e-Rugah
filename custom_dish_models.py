"""
Custom Dish Database Models
Separate database for custom dish searches
Uses the same db instance but with bind_key to separate database
"""
from datetime import datetime
from models import db

class CustomDish(db.Model):
    """Custom dishes that customers can search for"""
    __tablename__ = 'custom_dish'
    __bind_key__ = 'custom_dishes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    base_servings = db.Column(db.Integer, nullable=False)
    markup = db.Column(db.Float, nullable=False)  # percentage
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ingredients = db.relationship('CustomDishIngredient', backref='dish', lazy=True, cascade='all, delete-orphan')

class CustomIngredient(db.Model):
    """Ingredients for custom dishes"""
    __tablename__ = 'custom_ingredient'
    __bind_key__ = 'custom_dishes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(20), nullable=False)  # kg, g, L, ml, pcs
    unit_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CustomDishIngredient(db.Model):
    """Junction table linking custom dishes to ingredients"""
    __tablename__ = 'custom_dish_ingredient'
    __bind_key__ = 'custom_dishes'
    
    id = db.Column(db.Integer, primary_key=True)
    dish_id = db.Column(db.Integer, db.ForeignKey('custom_dish.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('custom_ingredient.id'), nullable=False)
    quantity_for_base_servings = db.Column(db.Float, nullable=False)
    
    ingredient = db.relationship('CustomIngredient', backref='dish_ingredients', lazy=True)