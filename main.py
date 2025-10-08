from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from sqlalchemy import func
from functools import wraps
import os
import json
import csv
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from models import db, User, Chef, Event, MenuItem, Booking, Payment, OTP, SystemConfig, Dish, Ingredient, DishIngredient, MpesaConfig, PasswordResetCode, Review, VerificationCode
from custom_dish_models import CustomDish, CustomIngredient, CustomDishIngredient
from payments import initiate_mpesa_stk, handle_mpesa_callback
from otp import generate_otp, verify_otp
from verification import send_email_code, send_sms_code, verify_code, is_sms_verification_enabled, SMS_VERIFICATION_KEY, send_password_reset_email, verify_password_reset_code, mark_reset_code_used

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SESSION_SECRET', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erugah.db'
app.config['SQLALCHEMY_BINDS'] = {
    'custom_dishes': 'sqlite:///dish.db'
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Remember Me configuration
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)  # Remember for 30 days
app.config['REMEMBER_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['REMEMBER_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access to cookie
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@app.context_processor
def inject_year():
    return {'year': datetime.now().year}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def role_required(role):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role != role:
                flash('Access denied. Insufficient permissions.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def index():
    # Show welcome page for non-logged-in users
    # Show full content (hero + all sections) for logged-in users
    featured_chefs = Chef.query.filter(
        Chef.is_verified.is_(True),
        Chef.is_approved.is_(True)
    ).order_by(
        Chef.is_featured.desc(),
        func.coalesce(Chef.featured_priority, 0).desc(),
        func.coalesce(Chef.rating_count, 0).desc(),
        func.coalesce(Chef.rating_total, 0).desc()
    ).limit(12).all()

    if current_user.is_authenticated:
        return render_template('index.html', featured_chefs=featured_chefs)
    else:
        return render_template('welcome.html', featured_chefs=featured_chefs)
        
@app.route('/reviews/<path:filename>')
def reviews_files(filename):
    return send_from_directory('reviews', filename)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'customer')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        user = User(email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Automatically log in the user after registration
        login_user(user)
        flash('Registration successful! Welcome to e-Rugah.', 'success')
        
        # Redirect to appropriate dashboard based on role
        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif user.role == 'chef':
            return redirect(url_for('chef_dashboard'))
        else:
            return redirect(url_for('customer_dashboard'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me') == 'on'
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            # Login user with remember me option
            # If remember_me is True, session will last for 30 days
            # If False, session expires when browser closes
            login_user(user, remember=remember_me)
            flash('Login successful!', 'success')
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'chef':
                return redirect(url_for('chef_dashboard'))
            else:
                return redirect(url_for('customer_dashboard'))
        
        flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        # Check if user exists
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('If an account exists with this email, a reset code will be sent.', 'info')
            return redirect(url_for('forgot_password'))
        
        # Send reset code
        success, code = send_password_reset_email(email)
        
        if success:
            # Store email in session for verification
            session['reset_email'] = email
            flash('A password reset code has been sent to your email.', 'success')
            return redirect(url_for('reset_password'))
        else:
            flash('Failed to send reset code. Please try again later.', 'danger')
    
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    # Check if email is in session
    if 'reset_email' not in session:
        flash('Please request a password reset first.', 'warning')
        return redirect(url_for('forgot_password'))
    
    email = session['reset_email']
    
    if request.method == 'POST':
        code = request.form.get('code')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate passwords match
        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', email=email)
        
        # Verify reset code
        is_valid, message = verify_password_reset_code(email, code)
        
        if not is_valid:
            flash(message, 'danger')
            return render_template('reset_password.html', email=email)
        
        # Update password
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(new_password)
            mark_reset_code_used(email, code)
            db.session.commit()
            
            # Clear session
            session.pop('reset_email', None)
            
            flash('Password reset successful! You can now login with your new password.', 'success')
            return redirect(url_for('login'))
        else:
            flash('User not found.', 'danger')
    
    return render_template('reset_password.html', email=email)

@app.route('/customer/dashboard')
@role_required('customer')
def customer_dashboard():
    events = Event.query.filter_by(customer_id=current_user.id).all()
    completed_bookings = Booking.query.join(Event).filter(
        Event.customer_id == current_user.id,
        Booking.status == 'confirmed',
        Event.event_date <= datetime.utcnow()
    ).all()

    pending_reviews = [booking for booking in completed_bookings if booking.rating_value is None]
    rated_bookings = [booking for booking in completed_bookings if booking.rating_value is not None]

    return render_template(
        'customer_dashboard.html',
        events=events,
        completed_bookings=completed_bookings,
        pending_reviews=pending_reviews,
        rated_bookings=rated_bookings
    )

@app.route('/customer/event/<int:event_id>/details')
@role_required('customer')
def event_details(event_id):
    event = Event.query.get_or_404(event_id)
    if event.customer_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    # Get dishes for the event
    dish_ids = event.menu_items.split(',') if event.menu_items else []
    dishes = []
    total_guests = event.adult_guests + event.child_guests
    
    for dish_id in dish_ids:
        dish = Dish.query.get(int(dish_id))
        if dish:
            # Calculate cost for this dish
            dish_ingredients = DishIngredient.query.filter_by(dish_id=dish.id).all()
            dish_cost = 0.0
            ingredients_list = []
            
            for di in dish_ingredients:
                ingredient = Ingredient.query.get(di.ingredient_id)
                scaled_quantity = (di.quantity_for_base_servings / dish.base_servings) * total_guests
                cost = scaled_quantity * ingredient.unit_price
                dish_cost += cost
                ingredients_list.append(ingredient.name)
            
            markup_amount = dish_cost * (dish.markup / 100)
            selling_price = dish_cost + markup_amount
            
            dishes.append({
                'name': dish.name,
                'ingredients': ', '.join(ingredients_list) if ingredients_list else dish.description or 'No ingredients listed',
                'total_price': selling_price,
                'description': dish.description
            })
    
    # Get booking if exists
    booking = Booking.query.filter_by(event_id=event.id).first()
    
    return render_template('event_details.html', event=event, menu_items=dishes, booking=booking)

@app.route('/customer/event/<int:event_id>/edit', methods=['GET', 'POST'])
@role_required('customer')
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.customer_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    # Get existing booking if any
    booking = Booking.query.filter_by(event_id=event.id).first()
    
    if request.method == 'POST':
        # Store old values for comparison
        old_total_cost = event.total_cost
        old_chef_id = booking.chef_id if booking else None
        
        # Get form data
        county = request.form.get('county')
        sub_county = request.form.get('sub_county')
        town = request.form.get('town')
        adult_guests = int(request.form.get('adult_guests', 0))
        child_guests = int(request.form.get('child_guests', 0))
        event_date_str = request.form.get('event_date')
        dishes = request.form.getlist('dishes')
        custom_dishes_json = request.form.get('custom_dishes', '[]')
        
        event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
        total_guests = adult_guests + child_guests
        
        # Calculate new cost for regular menu dishes
        total_cost = 0.0
        for dish_id in dishes:
            dish = Dish.query.get(int(dish_id))
            dish_ingredients = DishIngredient.query.filter_by(dish_id=dish.id).all()

            dish_cost = 0.0
            for di in dish_ingredients:
                ingredient = Ingredient.query.get(di.ingredient_id)
                scaled_quantity = (di.quantity_for_base_servings / dish.base_servings) * total_guests
                cost = scaled_quantity * ingredient.unit_price
                dish_cost += cost

            markup_amount = dish_cost * (dish.markup / 100)
            selling_price = dish_cost + markup_amount
            total_cost += selling_price
        
        # Calculate cost for custom dishes
        try:
            custom_dishes = json.loads(custom_dishes_json)
            for custom_dish_id in custom_dishes:
                dish = Dish.query.get(int(custom_dish_id))
                if dish:
                    dish_ingredients = DishIngredient.query.filter_by(dish_id=dish.id).all()
                    dish_cost = 0.0
                    for di in dish_ingredients:
                        ingredient = Ingredient.query.get(di.ingredient_id)
                        scaled_quantity = (di.quantity_for_base_servings / dish.base_servings) * total_guests
                        cost = scaled_quantity * ingredient.unit_price
                        dish_cost += cost
                    markup_amount = dish_cost * (dish.markup / 100)
                    selling_price = dish_cost + markup_amount
                    total_cost += selling_price
                    dishes.append(str(custom_dish_id))
        except:
            pass
        
        # Update event details
        event.county = county
        event.sub_county = sub_county
        event.town = town
        event.adult_guests = adult_guests
        event.child_guests = child_guests
        event.event_date = event_date
        event.menu_items = ','.join(dishes)
        event.total_cost = total_cost
        
        # Handle booking and payment adjustments
        if booking:
            # Get deposit percentage
            deposit_config = SystemConfig.query.filter_by(key='deposit_percentage').first()
            deposit_percentage = float(deposit_config.value) if deposit_config else 30.0
            
            # Calculate new deposit amount
            new_deposit_amount = (total_cost * deposit_percentage) / 100
            old_deposit_amount = booking.deposit_amount
            
            # Check if price increased
            if total_cost > old_total_cost:
                # Calculate additional deposit needed
                additional_deposit = new_deposit_amount - old_deposit_amount
                
                # Update booking deposit amount
                booking.deposit_amount = new_deposit_amount
                booking.status = 'pending'  # Reset to pending for additional payment
                
                db.session.commit()
                
                flash(f'Event updated! The total cost increased by KES {total_cost - old_total_cost:,.0f}. You need to pay an additional deposit of KES {additional_deposit:,.0f}.', 'warning')
                return redirect(url_for('pay_additional_deposit', booking_id=booking.id, additional_amount=additional_deposit))
            else:
                # Price stayed same or decreased - just update the event
                booking.deposit_amount = new_deposit_amount
                db.session.commit()
                
                flash('Event updated successfully! No additional payment required.', 'success')
                return redirect(url_for('match_chefs', event_id=event.id))
        else:
            # No booking yet, just update event
            db.session.commit()
            flash('Event updated successfully!', 'success')
            return redirect(url_for('match_chefs', event_id=event.id))
    
    # GET request - show edit form
    dishes = Dish.query.all()
    selected_dish_ids = event.menu_items.split(',') if event.menu_items else []
    
    return render_template('edit_event.html', event=event, dishes=dishes, selected_dish_ids=selected_dish_ids, booking=booking)

@app.route('/customer/create-event', methods=['GET', 'POST'])
@role_required('customer')
def create_event():
    if request.method == 'POST':
        county = request.form.get('county')
        sub_county = request.form.get('sub_county')
        town = request.form.get('town')
        adult_guests = int(request.form.get('adult_guests', 0))
        child_guests = int(request.form.get('child_guests', 0))
        event_date_str = request.form.get('event_date')
        dishes = request.form.getlist('dishes')
        custom_dishes_json = request.form.get('custom_dishes', '[]')
        
        event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
        total_guests = adult_guests + child_guests
        
        # Calculate cost for regular menu dishes
        total_cost = 0.0
        for dish_id in dishes:
            dish = Dish.query.get(int(dish_id))
            dish_ingredients = DishIngredient.query.filter_by(dish_id=dish.id).all()

            dish_cost = 0.0
            for di in dish_ingredients:
                ingredient = Ingredient.query.get(di.ingredient_id)
                scaled_quantity = (di.quantity_for_base_servings / dish.base_servings) * total_guests
                cost = scaled_quantity * ingredient.unit_price
                dish_cost += cost

            markup_amount = dish_cost * (dish.markup / 100)
            selling_price = dish_cost + markup_amount
            total_cost += selling_price
        
        # Calculate cost for custom dishes
        try:
            custom_dishes = json.loads(custom_dishes_json)
            for custom_dish_id in custom_dishes:
                dish = Dish.query.get(int(custom_dish_id))
                if dish:
                    dish_ingredients = DishIngredient.query.filter_by(dish_id=dish.id).all()
                    dish_cost = 0.0
                    for di in dish_ingredients:
                        ingredient = Ingredient.query.get(di.ingredient_id)
                        scaled_quantity = (di.quantity_for_base_servings / dish.base_servings) * total_guests
                        cost = scaled_quantity * ingredient.unit_price
                        dish_cost += cost
                    markup_amount = dish_cost * (dish.markup / 100)
                    selling_price = dish_cost + markup_amount
                    total_cost += selling_price
                    # Add custom dish to dishes list
                    dishes.append(str(custom_dish_id))
        except:
            pass  # If custom dishes parsing fails, continue with regular dishes only
        
        event = Event(
            customer_id=current_user.id,
            county=county,
            sub_county=sub_county,
            town=town,
            adult_guests=adult_guests,
            child_guests=child_guests,
            event_date=event_date,
            menu_items=','.join(dishes),
            total_cost=total_cost
        )
        db.session.add(event)
        db.session.commit()
        
        flash('Event created successfully!', 'success')
        return redirect(url_for('match_chefs', event_id=event.id))
    
    dishes = Dish.query.all()
    return render_template('create_event.html', dishes=dishes)

@app.route('/customer/event/<int:event_id>/match-chefs')
@role_required('customer')
def match_chefs(event_id):
    event = Event.query.get_or_404(event_id)
    if event.customer_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    chefs = Chef.query.filter_by(
        is_verified=True,
        is_approved=True,
        county=event.county,
        sub_county=event.sub_county,
        town=event.town
    ).all()
    
    if not chefs:
        chefs = Chef.query.filter_by(
            is_verified=True,
            is_approved=True,
            county=event.county,
            sub_county=event.sub_county
        ).all()
    
    if not chefs:
        chefs = Chef.query.filter_by(
            is_verified=True,
            is_approved=True,
            county=event.county
        ).all()
    
    return render_template('match_chefs.html', event=event, chefs=chefs)

@app.route('/customer/event/<int:event_id>/book/<int:chef_id>')
@role_required('customer')
def book_chef(event_id, chef_id):
    event = Event.query.get_or_404(event_id)
    chef = Chef.query.get_or_404(chef_id)
    
    if event.customer_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    deposit_config = SystemConfig.query.filter_by(key='deposit_percentage').first()
    deposit_percentage = float(deposit_config.value) if deposit_config else 30.0
    
    deposit_amount = (event.total_cost * deposit_percentage) / 100
    
    booking = Booking(
        event_id=event.id,
        chef_id=chef.id,
        deposit_amount=deposit_amount,
        status='pending'
    )
    db.session.add(booking)
    db.session.commit()
    
    flash('Chef selected! Please proceed to payment.', 'success')
    return redirect(url_for('pay_booking', booking_id=booking.id))

@app.route('/booking/<int:booking_id>/pay', methods=['GET', 'POST'])
@login_required
def pay_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    event = Event.query.get(booking.event_id)
    
    if event.customer_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    if request.method == 'POST':
        phone = request.form.get('phone')
        
        payment = Payment(
            booking_id=booking.id,
            phone_number=phone,
            amount=booking.deposit_amount,
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()
        
        result = initiate_mpesa_stk(phone, booking.deposit_amount, booking.id)
        
        if result.get('success'):
            flash('Payment initiated successfully! Please check your phone.', 'success')
            return redirect(url_for('payment_status', booking_id=booking.id))
        else:
            flash('Payment initiation failed. Please try again.', 'danger')
    
    return render_template('pay_booking.html', booking=booking, event=event)

@app.route('/booking/<int:booking_id>/payment-status')
@login_required
def payment_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    event = Event.query.get(booking.event_id)
    payment = Payment.query.filter_by(booking_id=booking.id).order_by(Payment.created_at.desc()).first()
    
    return render_template('payment_status.html', booking=booking, event=event, payment=payment)

@app.route('/booking/<int:booking_id>/pay-additional', methods=['GET', 'POST'])
@login_required
def pay_additional_deposit(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    event = Event.query.get(booking.event_id)
    
    if event.customer_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    # Get additional amount from query parameter
    additional_amount = float(request.args.get('additional_amount', 0))
    
    if request.method == 'POST':
        phone = request.form.get('phone')
        
        payment = Payment(
            booking_id=booking.id,
            phone_number=phone,
            amount=additional_amount,
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()
        
        result = initiate_mpesa_stk(phone, additional_amount, booking.id)
        
        if result.get('success'):
            flash('Additional payment initiated successfully! Please check your phone.', 'success')
            return redirect(url_for('payment_status', booking_id=booking.id))
        else:
            flash('Payment initiation failed. Please try again.', 'danger')
    
    return render_template('pay_additional_deposit.html', booking=booking, event=event, additional_amount=additional_amount)

@app.route('/mpesa/callback', methods=['POST'])
def mpesa_callback():
    callback_data = request.get_json()
    result = handle_mpesa_callback(callback_data)
    return jsonify(result)

@app.route('/chef/register', methods=['GET', 'POST'])
def chef_register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        phone = request.form.get('phone')
        county = request.form.get('county')
        sub_county = request.form.get('sub_county')
        town = request.form.get('town')
        about = request.form.get('about')
        meals = request.form.getlist('meals')

        if len(meals) > 5:
            return jsonify({
                'success': False,
                'message': 'Maximum 5 meals allowed'
            })

        if User.query.filter_by(email=email).first():
            return jsonify({
                'success': False,
                'message': 'Email already registered'
            })

        try:
            # Handle photo upload
            photo_url = None
            if 'photo' in request.files:
                photo = request.files['photo']
                if photo and photo.filename:
                    # Save photo with secure filename
                    filename = secure_filename(f"chef_{email}_{photo.filename}")
                    photo_path = os.path.join('static', 'images', 'chefs', filename)
                    os.makedirs(os.path.dirname(photo_path), exist_ok=True)
                    photo.save(photo_path)
                    # Store with /static/ prefix for consistency
                    photo_url = f"/static/images/chefs/{filename}"

            # Create user account immediately
            user = User(email=email, role='chef')
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # Get user.id without committing

            # Create chef profile
            chef = Chef(
                user_id=user.id,
                name=name,
                phone=phone,
                county=county,
                sub_county=sub_county,
                town=town,
                about=about,
                meals_offered=','.join(meals),
                photo_url=photo_url,
                is_verified=False,
                is_approved=False
            )
            db.session.add(chef)
            db.session.commit()

            # Log in the user
            login_user(user)

            # Store data in session for verification flow
            session['pending_verification'] = {
                'user_id': user.id,
                'email': email,
                'phone': phone,
                'sms_enabled': is_sms_verification_enabled()
            }

            # Return success response to trigger modal
            return jsonify({
                'success': True,
                'message': 'Account created! Please verify your email.',
                'sms_enabled': is_sms_verification_enabled()
            })
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Registration failed: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'message': f'Registration failed: {str(e)}'
            })

    return render_template('chef_register.html', sms_verification_enabled=is_sms_verification_enabled())

@app.route('/chef/verify-otp', methods=['GET', 'POST'])
def verify_otp_page():
    email = request.args.get('email') or request.form.get('email')
    
    if request.method == 'POST':
        code = request.form.get('code')
        
        success, message = verify_otp(email, code)
        
        if success:
            user = User.query.filter_by(email=email).first()
            if user and user.chef:
                user.chef.is_verified = True
                db.session.commit()
                # Automatically log in the chef after verification
                login_user(user)
                flash('Email verified successfully! Admin approval pending.', 'success')
                return redirect(url_for('chef_dashboard'))
        
        flash(message, 'danger')
    
    return render_template('verify_otp.html', email=email)

@app.route('/chef/pending')
@role_required('chef')
def chef_pending():
    chef = Chef.query.filter_by(user_id=current_user.id).first()
    if not chef:
        flash('Chef profile not found', 'danger')
        return redirect(url_for('index'))
    
    # If chef is already approved, redirect to dashboard
    if chef.is_approved:
        return redirect(url_for('chef_dashboard'))
    
    return render_template('chef_pending.html', chef=chef)

@app.route('/chef/dashboard')
@role_required('chef')
def chef_dashboard():
    chef = Chef.query.filter_by(user_id=current_user.id).first()
    if not chef:
        flash('Chef profile not found', 'danger')
        return redirect(url_for('index'))

    # If chef is not approved yet, redirect to pending page
    if not chef.is_approved:
        return redirect(url_for('chef_pending'))

    # Get chef's uploaded gallery images
    images = []
    chefs_dir = os.path.join('static', 'images', 'chefs')
    if os.path.exists(chefs_dir):
        for file in os.listdir(chefs_dir):
            if file.startswith(f"chef_{chef.id}_") and file.lower().endswith(('.png', '.jpg', '.jpeg')):
                images.append(file)

    bookings = Booking.query.filter_by(chef_id=chef.id).all()
    return render_template('chef_dashboard.html', chef=chef, bookings=bookings, images=images)

@app.route('/chef/profile/<int:chef_id>')
@login_required
def chef_profile(chef_id):
    chef = Chef.query.get_or_404(chef_id)

    # Allow customers to view approved chefs
    if current_user.role == 'customer' and not chef.is_approved:
        flash('Chef profile not available', 'danger')
        return redirect(url_for('customer_dashboard'))

    # Get chef's uploaded images
    images = []
    chefs_dir = os.path.join('static', 'images', 'chefs')
    if os.path.exists(chefs_dir):
        for file in os.listdir(chefs_dir):
            if file.startswith(f"chef_{chef.id}_") and file.lower().endswith(('.png', '.jpg', '.jpeg')):
                images.append(file)

    return render_template('chef_profile.html', chef=chef, images=images)

@app.route('/chef/upload-image', methods=['POST'])
@role_required('chef')
def chef_upload_image():
    if 'image' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('chef_dashboard'))

    file = request.files['image']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('chef_dashboard'))

    if file:
        from werkzeug.utils import secure_filename
        # Get the chef profile to use chef.id instead of user.id
        chef = Chef.query.filter_by(user_id=current_user.id).first()
        if not chef:
            flash('Chef profile not found', 'danger')
            return redirect(url_for('chef_dashboard'))
        
        filename = secure_filename(f"chef_{chef.id}_{file.filename}")
        file_path = os.path.join('static', 'images', 'chefs', filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        flash('Image uploaded successfully!', 'success')

    return redirect(url_for('chef_dashboard'))

@app.route('/chef/update-profile-photo', methods=['POST'])
@role_required('chef')
def chef_update_profile_photo():
    if 'profile_photo' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('chef_dashboard'))

    file = request.files['profile_photo']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('chef_dashboard'))

    if file:
        from werkzeug.utils import secure_filename
        chef = Chef.query.filter_by(user_id=current_user.id).first()
        if not chef:
            flash('Chef profile not found', 'danger')
            return redirect(url_for('chef_dashboard'))
        
        # Remove old profile photo if it exists
        if chef.photo_url:
            existing_path = chef.photo_url.lstrip('/')
            if os.path.exists(existing_path):
                try:
                    os.remove(existing_path)
                except OSError:
                    pass
        
        # Create a unique filename for the profile photo using chef.id to prevent special character issues
        original_name = os.path.splitext(secure_filename(file.filename))[0]
        extension = os.path.splitext(file.filename)[1]
        filename = secure_filename(f"chef_{chef.id}_{original_name}{extension}")
        file_path = os.path.join('static', 'images', 'chefs', filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        
        # Update the chef's photo_url in the database
        chef.photo_url = f"/static/images/chefs/{filename}"
        db.session.commit()
        
        flash('Profile photo updated successfully!', 'success')

    return redirect(url_for('chef_dashboard'))

@app.route('/api/chef/<int:chef_id>/profile')
def get_chef_profile_api(chef_id):
    """API endpoint to get chef profile data with images"""
    chef = Chef.query.get_or_404(chef_id)
    
    # Only show approved chefs
    if not chef.is_approved:
        return jsonify({'error': 'Chef profile not available'}), 404
    
    # Get chef's uploaded images
    images = []
    chefs_dir = os.path.join('static', 'images', 'chefs')
    if os.path.exists(chefs_dir):
        for file in os.listdir(chefs_dir):
            if file.startswith(f"chef_{chef.id}_") and file.lower().endswith(('.png', '.jpg', '.jpeg')):
                images.append(file)
    
    return jsonify({
        'id': chef.id,
        'name': chef.name,
        'email': chef.user.email,
        'phone': chef.phone,
        'location': chef.location,
        'bio': chef.about,
        'photo_url': chef.photo_url,
        'images': images
    })

@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    pending_chefs = Chef.query.filter_by(is_verified=True, is_approved=False).all()
    approved_chefs = Chef.query.filter_by(is_approved=True).all()
    total_bookings = Booking.query.count()
    confirmed_bookings = Booking.query.filter_by(status='confirmed').count()
    
    return render_template('admin_dashboard.html',
                         pending_chefs=pending_chefs,
                         approved_chefs=approved_chefs,
                         total_bookings=total_bookings,
                         confirmed_bookings=confirmed_bookings)

def send_chef_approval_email(chef):
    """Send approval email to chef with login credentials"""
    try:
        # Get email configuration from database
        email_configs = SystemConfig.query.filter(SystemConfig.key.in_([
            'gmail_user', 'gmail_password', 'smtp_host', 'smtp_port', 
            'smtp_encryption', 'sender_name', 'email_timeout'
        ])).all()
        
        config_dict = {config.key: config.value for config in email_configs}
        
        gmail_user = config_dict.get('gmail_user')
        gmail_password = config_dict.get('gmail_password')
        smtp_host = config_dict.get('smtp_host', 'smtp.gmail.com')
        smtp_port = int(config_dict.get('smtp_port', 587))
        smtp_encryption = config_dict.get('smtp_encryption', 'tls')
        sender_name = config_dict.get('sender_name', 'e-Rugah')
        email_timeout = int(config_dict.get('email_timeout', 30))
        
        if not gmail_user or not gmail_password:
            print("[ERROR] Email system not configured")
            return False
        
        # Send email using SMTP
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import smtplib
        
        msg = MIMEMultipart('alternative')
        msg['From'] = f'{sender_name} <{gmail_user}>'
        msg['To'] = chef.user.email
        msg['Subject'] = '🎉 Congratulations! Your e-Rugah Chef Account is Approved'
        
        # Plain text version
        text_body = f"""
Dear {chef.name},

Congratulations! We are thrilled to inform you that your chef application has been approved!

Your Login Credentials:
Email: {chef.user.email}
Password: [The password you created during registration]

You can now log in to your chef dashboard and start:
- Managing your profile
- Accepting booking requests
- Showcasing your culinary expertise
- Connecting with food lovers

Login here: {request.url_root}login

Welcome to the e-Rugah family! We're excited to have you on board.

Best regards,
The e-Rugah Team

---
This is an automated message from e-Rugah
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        # HTML version
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: #ff6b35; margin: 0; font-size: 28px;">🎉 Congratulations!</h1>
                    </div>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6;">Dear <strong>{chef.name}</strong>,</p>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6;">
                        We are thrilled to inform you that your chef application has been <strong style="color: #10b981;">approved</strong>!
                    </p>
                    
                    <div style="background: linear-gradient(135deg, #fff8f5 0%, #ffe8dc 100%); padding: 25px; border-radius: 10px; margin: 25px 0; border-left: 4px solid #ff6b35;">
                        <h3 style="color: #ff6b35; margin-top: 0; margin-bottom: 15px;">Your Login Credentials</h3>
                        <p style="margin: 10px 0; color: #333;"><strong>Email:</strong> <span style="color: #ff6b35;">{chef.user.email}</span></p>
                        <p style="margin: 10px 0; color: #333;"><strong>Password:</strong> [The password you created during registration]</p>
                    </div>
                    
                    <div style="margin: 25px 0;">
                        <h3 style="color: #333; margin-bottom: 15px;">You can now:</h3>
                        <ul style="color: #666; line-height: 1.8;">
                            <li>✅ Manage your profile</li>
                            <li>✅ Accept booking requests</li>
                            <li>✅ Showcase your culinary expertise</li>
                            <li>✅ Connect with food lovers</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{request.url_root}login" style="display: inline-block; background: linear-gradient(135deg, #ff6b35, #ff8c42); color: white; padding: 15px 40px; text-decoration: none; border-radius: 25px; font-weight: bold; font-size: 16px; box-shadow: 0 4px 15px rgba(255, 107, 53, 0.3);">
                            Login to Dashboard
                        </a>
                    </div>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6; margin-top: 30px;">
                        Welcome to the e-Rugah family! We're excited to have you on board.
                    </p>
                    
                    <p style="font-size: 16px; color: #333; line-height: 1.6;">
                        Best regards,<br>
                        <strong style="color: #ff6b35;">The e-Rugah Team</strong>
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    
                    <p style="color: #999; font-size: 12px; text-align: center; margin: 10px 0;">
                        This is an automated message from e-Rugah<br>
                        Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    </p>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email with configured settings
        if smtp_encryption == 'ssl':
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=email_timeout)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=email_timeout)
            if smtp_encryption == 'tls':
                server.starttls()
        
        server.login(gmail_user, gmail_password)
        server.send_message(msg)
        server.quit()
        
        print(f"[SUCCESS] Approval email sent to {chef.user.email}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to send approval email: {e}")
        import traceback
        traceback.print_exc()
        return False

@app.route('/admin/chef/<int:chef_id>/approve')
@role_required('admin')
def approve_chef(chef_id):
    chef = Chef.query.get_or_404(chef_id)
    chef.is_approved = True
    db.session.commit()
    
    # Send approval email to chef
    email_sent = send_chef_approval_email(chef)
    
    if email_sent:
        flash(f'Chef {chef.name} approved successfully! Approval email sent.', 'success')
    else:
        flash(f'Chef {chef.name} approved successfully! (Email notification failed)', 'warning')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/chef/<int:chef_id>/reject')
@role_required('admin')
def reject_chef(chef_id):
    chef = Chef.query.get_or_404(chef_id)
    chef.is_approved = False
    db.session.commit()
    flash(f'Chef {chef.name} rejected.', 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/menu', methods=['GET', 'POST'])
@role_required('admin')
def manage_menu():
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        price = float(request.form.get('price'))
        ingredients = request.form.get('ingredients')
        
        menu_item = MenuItem(
            name=name,
            category=category,
            price_per_person=price,
            ingredients=ingredients
        )
        db.session.add(menu_item)
        db.session.commit()
        flash('Menu item added successfully!', 'success')
        return redirect(url_for('manage_menu'))
    
    menu_items = MenuItem.query.all()
    return render_template('manage_menu.html', menu_items=menu_items)

@app.route('/admin/menu/<int:item_id>/delete')
@role_required('admin')
def delete_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash('Menu item deleted successfully!', 'success')
    return redirect(url_for('manage_menu'))

@app.route('/admin/create-dish', methods=['GET', 'POST'])
@role_required('admin')
def admin_create_dish():
    if request.method == 'POST':
        name = request.form.get('name')
        base_servings = int(request.form.get('base_servings'))
        markup = float(request.form.get('markup'))
        description = request.form.get('description')

        dish = Dish(name=name, base_servings=base_servings, markup=markup, description=description)
        db.session.add(dish)
        db.session.commit()

        # Handle ingredients
        ingredient_names = request.form.getlist('ingredient_name[]')
        units = request.form.getlist('unit[]')
        unit_prices = request.form.getlist('unit_price[]')
        quantities = request.form.getlist('quantity[]')

        for i in range(len(ingredient_names)):
            if ingredient_names[i].strip():
                # Check if ingredient exists, else create
                ingredient = Ingredient.query.filter_by(name=ingredient_names[i].strip()).first()
                if not ingredient:
                    ingredient = Ingredient(name=ingredient_names[i].strip(), unit=units[i], unit_price=float(unit_prices[i]))
                    db.session.add(ingredient)
                    db.session.commit()

                dish_ingredient = DishIngredient(dish_id=dish.id, ingredient_id=ingredient.id, quantity_for_base_servings=float(quantities[i]))
                db.session.add(dish_ingredient)

        db.session.commit()
        flash('Dish created successfully!', 'success')
        return redirect(url_for('admin_create_dish'))

    dishes = Dish.query.all()
    ingredients = Ingredient.query.all()
    return render_template('admin_create_dish.html', dishes=dishes, ingredients=ingredients)

@app.route('/admin/delete-dish/<int:dish_id>', methods=['POST'])
@role_required('admin')
def admin_delete_dish(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    
    # Delete associated dish ingredients first
    DishIngredient.query.filter_by(dish_id=dish_id).delete()
    
    # Delete the dish
    db.session.delete(dish)
    db.session.commit()
    
    flash(f'Dish "{dish.name}" deleted successfully!', 'success')
    return redirect(url_for('admin_create_dish'))

# ============================================
# CUSTOM DISH DATABASE MANAGEMENT (dish.db)
# ============================================

@app.route('/admin/custom-dish-database', methods=['GET', 'POST'])
@role_required('admin')
def admin_custom_dish_database():
    """Manage custom dish database for customer searches"""
    if request.method == 'POST':
        name = request.form.get('name')
        base_servings = int(request.form.get('base_servings'))
        markup = float(request.form.get('markup'))
        description = request.form.get('description')

        dish = CustomDish(name=name, base_servings=base_servings, markup=markup, description=description)
        db.session.add(dish)
        db.session.commit()

        # Handle ingredients
        ingredient_names = request.form.getlist('ingredient_name[]')
        units = request.form.getlist('unit[]')
        unit_prices = request.form.getlist('unit_price[]')
        quantities = request.form.getlist('quantity[]')

        for i in range(len(ingredient_names)):
            if ingredient_names[i].strip():
                # Check if ingredient exists in custom database, else create
                ingredient = CustomIngredient.query.filter_by(name=ingredient_names[i].strip()).first()
                if not ingredient:
                    ingredient = CustomIngredient(name=ingredient_names[i].strip(), unit=units[i], unit_price=float(unit_prices[i]))
                    db.session.add(ingredient)
                    db.session.commit()

                dish_ingredient = CustomDishIngredient(dish_id=dish.id, ingredient_id=ingredient.id, quantity_for_base_servings=float(quantities[i]))
                db.session.add(dish_ingredient)

        db.session.commit()
        flash('Custom dish added to database successfully!', 'success')
        return redirect(url_for('admin_custom_dish_database'))

    dishes = CustomDish.query.all()
    ingredients = CustomIngredient.query.all()
    return render_template('admin_custom_dish_database.html', dishes=dishes, ingredients=ingredients)

@app.route('/admin/delete-custom-dish/<int:dish_id>', methods=['POST'])
@role_required('admin')
def admin_delete_custom_dish(dish_id):
    """Delete a custom dish from the database"""
    dish = CustomDish.query.get_or_404(dish_id)
    
    # Delete associated dish ingredients first
    CustomDishIngredient.query.filter_by(dish_id=dish_id).delete()
    
    # Delete the dish
    db.session.delete(dish)
    db.session.commit()
    
    flash(f'Custom dish "{dish.name}" deleted successfully!', 'success')
    return redirect(url_for('admin_custom_dish_database'))

@app.route('/api/calculate-dish-price', methods=['POST'])
@login_required
def calculate_dish_price():
    dish_id_str = request.form.get('dish_id')
    guests = int(request.form.get('guests'))

    # Check if this is a custom dish (prefixed with 'custom_')
    is_custom = str(dish_id_str).startswith('custom_')
    
    if is_custom:
        # Extract the actual ID from 'custom_123' format
        actual_id = int(dish_id_str.replace('custom_', ''))
        dish = CustomDish.query.get_or_404(actual_id)
        dish_ingredients = CustomDishIngredient.query.filter_by(dish_id=dish.id).all()
        
        total_cost = 0.0
        ingredient_breakdown = []

        for di in dish_ingredients:
            ingredient = CustomIngredient.query.get(di.ingredient_id)
            scaled_quantity = (di.quantity_for_base_servings / dish.base_servings) * guests
            cost = scaled_quantity * ingredient.unit_price
            total_cost += cost
            ingredient_breakdown.append({
                'name': ingredient.name,
                'scaled_quantity': round(scaled_quantity, 2),
                'unit': ingredient.unit,
                'cost': round(cost, 2)
            })
    else:
        # Regular dish from main database
        dish_id = int(dish_id_str)
        dish = Dish.query.get_or_404(dish_id)
        dish_ingredients = DishIngredient.query.filter_by(dish_id=dish.id).all()

        total_cost = 0.0
        ingredient_breakdown = []

        for di in dish_ingredients:
            ingredient = Ingredient.query.get(di.ingredient_id)
            scaled_quantity = (di.quantity_for_base_servings / dish.base_servings) * guests
            cost = scaled_quantity * ingredient.unit_price
            total_cost += cost
            ingredient_breakdown.append({
                'name': ingredient.name,
                'scaled_quantity': round(scaled_quantity, 2),
                'unit': ingredient.unit,
                'cost': round(cost, 2)
            })

    markup_amount = total_cost * (dish.markup / 100)
    selling_price = total_cost + markup_amount

    return jsonify({
        'dish_name': dish.name,
        'guests': guests,
        'ingredient_breakdown': ingredient_breakdown,
        'total_cost': round(total_cost, 2),
        'markup_percentage': dish.markup,
        'markup_amount': round(markup_amount, 2),
        'selling_price': round(selling_price, 2)
    })

@app.route('/api/check-custom-dish', methods=['POST'])
@login_required
def check_custom_dish():
    """Check if a custom dish exists in the custom dish database and return its details"""
    dish_name = request.form.get('dish_name', '').strip()
    
    if not dish_name:
        return jsonify({'success': False, 'message': 'Please enter a dish name'})
    
    # Search for dish in custom dish database (case-insensitive)
    dish = CustomDish.query.filter(CustomDish.name.ilike(f'%{dish_name}%')).first()
    
    if not dish:
        return jsonify({
            'success': False, 
            'found': False,
            'message': f'"{dish_name}" is not in our custom menu database'
        })
    
    # Get dish ingredients from custom dish database
    dish_ingredients = CustomDishIngredient.query.filter_by(dish_id=dish.id).all()
    
    ingredients_list = []
    total_base_cost = 0.0
    
    for di in dish_ingredients:
        ingredient = CustomIngredient.query.get(di.ingredient_id)
        ingredient_cost = di.quantity_for_base_servings * ingredient.unit_price
        total_base_cost += ingredient_cost
        
        ingredients_list.append({
            'name': ingredient.name,
            'quantity': di.quantity_for_base_servings,
            'unit': ingredient.unit,
            'unit_price': ingredient.unit_price,
            'total_cost': round(ingredient_cost, 2)
        })
    
    markup_amount = total_base_cost * (dish.markup / 100)
    base_selling_price = total_base_cost + markup_amount
    
    return jsonify({
        'success': True,
        'found': True,
        'dish': {
            'id': f'custom_{dish.id}',  # Prefix with 'custom_' to distinguish from regular dishes
            'name': dish.name,
            'description': dish.description,
            'base_servings': dish.base_servings,
            'markup': dish.markup,
            'ingredients': ingredients_list,
            'total_base_cost': round(total_base_cost, 2),
            'markup_amount': round(markup_amount, 2),
            'base_selling_price': round(base_selling_price, 2)
        }
    })

@app.route('/api/request-custom-dish', methods=['POST'])
@login_required
def request_custom_dish():
    """Send email request for a custom dish not in the database"""
    dish_name = request.form.get('dish_name', '').strip()
    additional_notes = request.form.get('notes', '').strip()
    
    if not dish_name:
        return jsonify({'success': False, 'message': 'Please enter a dish name'})
    
    # Get admin email from system config
    gmail_user = SystemConfig.query.filter_by(key='gmail_user').first()
    gmail_password = SystemConfig.query.filter_by(key='gmail_password').first()
    
    if not gmail_user or not gmail_password:
        return jsonify({
            'success': False, 
            'message': 'Email system not configured. Please contact administrator.'
        })
    
    # Send email to admin
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import smtplib
    
    msg = MIMEMultipart()
    msg['From'] = gmail_user.value
    msg['To'] = gmail_user.value  # Send to admin email
    msg['Subject'] = f'Custom Dish Request - {dish_name}'
    
    body = f"""
    Custom Dish Request from e-Rugah Customer
    
    Customer: {current_user.email}
    Requested Dish: {dish_name}
    Additional Notes: {additional_notes if additional_notes else 'None'}
    
    Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    Please review this request and add the dish to the menu if appropriate.
    
    Best regards,
    e-Rugah System
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user.value, gmail_password.value)
        text = msg.as_string()
        server.sendmail(gmail_user.value, gmail_user.value, text)
        server.quit()
        
        return jsonify({
            'success': True, 
            'message': 'Your request has been sent to the administrator. We will review and add it to our menu soon!'
        })
    except Exception as e:
        print(f"[ERROR] Failed to send custom dish request email: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to send request. Please try again later.'
        })

@app.route('/admin/config', methods=['GET', 'POST'])
@role_required('admin')
def config():
    if request.method == 'POST':
        deposit_percentage = request.form.get('deposit_percentage')
        
        config = SystemConfig.query.filter_by(key='deposit_percentage').first()
        if config:
            config.value = deposit_percentage
        else:
            config = SystemConfig(key='deposit_percentage', value=deposit_percentage)
            db.session.add(config)
        
        db.session.commit()
        flash('Configuration updated successfully!', 'success')
        return redirect(url_for('config'))
    
    deposit_config = SystemConfig.query.filter_by(key='deposit_percentage').first()
    deposit_percentage = deposit_config.value if deposit_config else '30'
    
    return render_template('config.html', deposit_percentage=deposit_percentage)

@app.route('/admin/reports')
@role_required('admin')
def reports():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    chef_id = request.args.get('chef_id')
    county = request.args.get('county')
    
    query = db.session.query(Booking, Event, Chef, Payment).join(
        Event, Booking.event_id == Event.id
    ).join(
        Chef, Booking.chef_id == Chef.id
    ).outerjoin(
        Payment, Booking.id == Payment.booking_id
    )
    
    if start_date:
        query = query.filter(Booking.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Booking.created_at <= datetime.strptime(end_date, '%Y-%m-%d'))
    if chef_id:
        query = query.filter(Booking.chef_id == int(chef_id))
    if county:
        query = query.filter(Event.county == county)
    
    results = query.all()
    chefs = Chef.query.filter_by(is_approved=True).all()
    
    total_deposits = sum(r.Payment.amount for r in results if r.Payment and r.Payment.status == 'success')
    
    return render_template('reports.html',
                         results=results,
                         chefs=chefs,
                         total_deposits=total_deposits,
                         start_date=start_date,
                         end_date=end_date,
                         chef_id=chef_id,
                         county=county)

@app.route('/admin/reports/export-csv')
@role_required('admin')
def export_csv():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = db.session.query(Booking, Event, Chef, Payment).join(
        Event, Booking.event_id == Event.id
    ).join(
        Chef, Booking.chef_id == Chef.id
    ).outerjoin(
        Payment, Booking.id == Payment.booking_id
    )
    
    if start_date:
        query = query.filter(Booking.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Booking.created_at <= datetime.strptime(end_date, '%Y-%m-%d'))
    
    results = query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Booking ID', 'Event Date', 'Chef Name', 'Location', 'Guests', 'Total Cost', 'Deposit', 'Status', 'Payment Status'])
    
    for booking, event, chef, payment in results:
        writer.writerow([
            booking.id,
            event.event_date.strftime('%Y-%m-%d'),
            chef.name,
            f"{event.county}, {event.sub_county}, {event.town}",
            event.adult_guests + event.child_guests,
            event.total_cost,
            booking.deposit_amount,
            booking.status,
            payment.status if payment else 'N/A'
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='bookings_report.csv'
    )

@app.route('/admin/reports/export-pdf')
@role_required('admin')
def export_pdf():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = db.session.query(Booking, Event, Chef, Payment).join(
        Event, Booking.event_id == Event.id
    ).join(
        Chef, Booking.chef_id == Chef.id
    ).outerjoin(
        Payment, Booking.id == Payment.booking_id
    )
    
    if start_date:
        query = query.filter(Booking.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Booking.created_at <= datetime.strptime(end_date, '%Y-%m-%d'))
    
    results = query.all()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph("e-Rugah Bookings Report", styles['Title']))
    elements.append(Spacer(1, 12))
    
    data = [['Booking ID', 'Event Date', 'Chef', 'Guests', 'Cost', 'Status']]
    for booking, event, chef, payment in results:
        data.append([
            str(booking.id),
            event.event_date.strftime('%Y-%m-%d'),
            chef.name,
            str(event.adult_guests + event.child_guests),
            f"KES {event.total_cost:.2f}",
            booking.status
        ])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='bookings_report.pdf'
    )

def complete_chef_registration_from_session():
    """Create the chef account from session data and return a JSON response."""
    reg_data = session.get('chef_registration')
    if not reg_data:
        return jsonify({'success': False, 'message': 'Registration data not found'})

    try:
        user = User(email=reg_data['email'], role='chef')
        user.set_password(reg_data['password'])
        db.session.add(user)
        db.session.flush()

        chef = Chef(
            user_id=user.id,
            name=reg_data['name'],
            phone=reg_data['phone'],
            county=reg_data['county'],
            sub_county=reg_data['sub_county'],
            town=reg_data['town'],
            about=reg_data['about'],
            meals_offered=','.join(reg_data['meals']),
            photo_url=reg_data['photo_url'],
            is_verified=True,
            is_approved=False
        )
        db.session.add(chef)
        db.session.commit()

        session.pop('chef_registration', None)
        login_user(user)

        return jsonify({'success': True, 'message': 'Registration completed successfully! Awaiting admin approval.', 'redirect': '/chef/pending'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Registration failed. Please try again.'})


@app.route('/send_email_code', methods=['POST'])
def send_email_code_endpoint():
    email = request.json.get('email')
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'})

    try:
        # Send email and get the code
        success, code = send_email_code(email)
        
        # Log the code for server-side debugging
        print(f"[DEBUG] Email verification code for {email}: {code}")
        
        # Return appropriate message based on whether email was sent
        if success:
            message = 'Verification code sent to your email'
            return jsonify({'success': True, 'message': message})
        else:
            # Email sending failed (likely missing credentials)
            return jsonify({
                'success': False, 
                'message': 'Failed to send email. Please check email configuration.'
            })
    except ValueError as e:
        print(f"[ERROR] ValueError: {e}")
        return jsonify({'success': False, 'message': str(e)})
    except Exception as e:
        print(f"[ERROR] Exception sending email code: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An error occurred while sending the code'})

@app.route('/verify_email_code', methods=['POST'])
def verify_email_code_endpoint():
    email = request.json.get('email')
    code = request.json.get('code')

    if not email or not code:
        return jsonify({'success': False, 'message': 'Email and code are required'})

    # Debug logging
    print(f"Verifying email code for: {email}, code: {code}")
    
    success, message = verify_code(email, code, 'email')
    
    # Debug logging
    print(f"Verification result: success={success}, message={message}")
    
    if not success:
        return jsonify({'success': False, 'message': message})

    # Mark email as verified in database
    user = User.query.filter_by(email=email).first()
    if user:
        user.email_verified = True
        db.session.commit()
        print(f"[SUCCESS] Email verified for user: {email}")

    # Check if SMS verification is required
    sms_enabled = is_sms_verification_enabled()
    chef_verified = False
    
    if sms_enabled:
        response_payload = {
            'success': True,
            'message': 'Email verified! Please verify your phone number.',
            'require_sms': True,
            'chef_verified': False
        }
        return jsonify(response_payload)
    else:
        # SMS disabled, mark chef as verified and build response
        if user and user.chef:
            user.chef.is_verified = True
            db.session.commit()
            chef_verified = True
        
        return jsonify({
            'success': True,
            'message': 'Email verified successfully!',
            'require_sms': False,
            'redirect': '/chef/dashboard',
            'chef_verified': chef_verified
        })

@app.route('/send_sms_code', methods=['POST'])
def send_sms_code_endpoint():
    if not is_sms_verification_enabled():
        return jsonify({'success': False, 'message': 'SMS verification is currently disabled.'})

    phone = request.json.get('phone')
    if not phone:
        return jsonify({'success': False, 'message': 'Phone number is required'})

    try:
        # Send SMS and get the code
        success, code = send_sms_code(phone)
        
        # Log the code for server-side debugging
        print(f"[DEBUG] SMS verification code for {phone}: {code}")
        
        # Return appropriate message based on whether SMS was sent
        if success:
            message = 'Verification code sent to your phone'
            return jsonify({'success': True, 'message': message})
        else:
            # SMS sending failed (likely missing credentials)
            return jsonify({
                'success': False,
                'message': 'Failed to send SMS. Please check SMS configuration.'
            })
    except ValueError as e:
        print(f"[ERROR] ValueError: {e}")
        return jsonify({'success': False, 'message': str(e)})
    except Exception as e:
        print(f"[ERROR] Exception sending SMS code: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An error occurred while sending the code'})


@app.route('/verify_sms_code', methods=['POST'])
def verify_sms_code_endpoint():
    if not is_sms_verification_enabled():
        return jsonify({'success': False, 'message': 'SMS verification is currently disabled.'})

    phone = request.json.get('phone')
    code = request.json.get('code')

    if not phone or not code:
        return jsonify({'success': False, 'message': 'Phone and code are required'})

    success, message = verify_code(phone, code, 'sms')
    
    if success:
        # Mark SMS as verified
        user = User.query.filter_by(id=current_user.id).first()
        if user:
            user.sms_verified = True
            
            # Check if email is also verified
            if user.email_verified:
                # Both verified - mark chef as fully verified
                if user.chef:
                    user.chef.is_verified = True
                db.session.commit()
                print(f"[SUCCESS] SMS verified for user: {user.email}, all verifications complete")
                return jsonify({
                    'success': True,
                    'message': 'SMS verified successfully!',
                    'redirect': '/chef/dashboard'
                })
            else:
                # SMS verified but email not yet verified
                db.session.commit()
                print(f"[SUCCESS] SMS verified for user: {user.email}, email verification still needed")
                return jsonify({
                    'success': True,
                    'message': 'SMS verified! Please verify your email to complete registration.',
                    'require_email': True
                })
        
        return jsonify({
            'success': True,
            'message': 'SMS verified successfully!',
            'redirect': '/chef/dashboard'
        })

    return jsonify({'success': False, 'message': message})

@app.route('/debug/verification-codes')
@role_required('admin')
def debug_verification_codes():
    """Debug endpoint to view verification codes"""
    codes = VerificationCode.query.order_by(VerificationCode.created_at.desc()).limit(10).all()
    result = []
    for code in codes:
        result.append({
            'identifier': code.identifier,
            'code': code.code,
            'type': code.type,
            'is_used': code.is_used,
            'expires_at': code.expires_at.strftime('%Y-%m-%d %H:%M:%S'),
            'created_at': code.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify(result)

@app.route('/admin/settings', methods=['GET', 'POST'])
@role_required('admin')
def admin_settings():
    if request.method == 'POST':
        # Save settings
        settings_keys = [
            'gmail_user', 'gmail_password',
            'sms_provider', 'sms_api_key', 'sms_api_secret', 'sms_sender_id',
            'deposit_percentage'
        ]

        for key in settings_keys:
            value = request.form.get(key)
            if value is not None:
                config = SystemConfig.query.filter_by(key=key).first()
                if config:
                    config.value = value
                else:
                    config = SystemConfig(key=key, value=value)
                    db.session.add(config)
        
        # Handle SMS verification toggle (checkbox)
        # Checkbox sends 'true' when checked, nothing when unchecked
        sms_enabled = request.form.get(SMS_VERIFICATION_KEY)
        sms_config = SystemConfig.query.filter_by(key=SMS_VERIFICATION_KEY).first()
        if sms_config:
            sms_config.value = 'true' if sms_enabled else 'false'
        else:
            sms_config = SystemConfig(key=SMS_VERIFICATION_KEY, value='true' if sms_enabled else 'false')
            db.session.add(sms_config)

        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    # Get current settings
    settings = {}
    configs = SystemConfig.query.filter(SystemConfig.key.in_([
        'gmail_user', 'gmail_password',
        'sms_provider', 'sms_api_key', 'sms_api_secret', 'sms_sender_id',
        'deposit_percentage', SMS_VERIFICATION_KEY
    ])).all()

    for config in configs:
        settings[config.key] = config.value

    return render_template('admin_settings.html', settings=settings, SMS_VERIFICATION_KEY=SMS_VERIFICATION_KEY)

@app.route('/admin/email-settings', methods=['GET', 'POST'])
@role_required('admin')
def admin_email_settings():
    if request.method == 'POST':
        # Save email settings
        email_settings_keys = [
            'gmail_user', 'gmail_password',
            'smtp_host', 'smtp_port', 'smtp_encryption',
            'admin_email', 'sender_name', 'email_timeout'
        ]

        for key in email_settings_keys:
            value = request.form.get(key)
            if value is not None:
                config = SystemConfig.query.filter_by(key=key).first()
                if config:
                    config.value = value
                else:
                    config = SystemConfig(key=key, value=value)
                    db.session.add(config)

        db.session.commit()
        flash('Email settings updated successfully!', 'success')
        return redirect(url_for('admin_email_settings'))

    # Get current settings
    settings = {}
    configs = SystemConfig.query.filter(SystemConfig.key.in_([
        'gmail_user', 'gmail_password',
        'smtp_host', 'smtp_port', 'smtp_encryption',
        'admin_email', 'sender_name', 'email_timeout'
    ])).all()

    for config in configs:
        settings[config.key] = config.value

    # Set defaults if not configured
    if 'smtp_host' not in settings:
        settings['smtp_host'] = 'smtp.gmail.com'
    if 'smtp_port' not in settings:
        settings['smtp_port'] = '587'
    if 'smtp_encryption' not in settings:
        settings['smtp_encryption'] = 'tls'
    if 'sender_name' not in settings:
        settings['sender_name'] = 'e-Rugah Contact Form'
    if 'email_timeout' not in settings:
        settings['email_timeout'] = '30'

    return render_template('admin_email_settings.html', settings=settings)

@app.route('/admin/test-email-connection', methods=['POST'])
@role_required('admin')
def test_email_connection():
    """Test SMTP connection with provided settings"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        # Get settings from form
        gmail_user = request.form.get('gmail_user')
        gmail_password = request.form.get('gmail_password')
        smtp_host = request.form.get('smtp_host', 'smtp.gmail.com')
        smtp_port = int(request.form.get('smtp_port', 587))
        smtp_encryption = request.form.get('smtp_encryption', 'tls')
        timeout = int(request.form.get('email_timeout', 30))
        
        if not gmail_user or not gmail_password:
            return jsonify({
                'success': False,
                'message': 'Gmail email and password are required'
            })
        
        # Test connection
        if smtp_encryption == 'ssl':
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=timeout)
            if smtp_encryption == 'tls':
                server.starttls()
        
        # Login
        server.login(gmail_user, gmail_password)
        
        # Send test email to self
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = gmail_user
        msg['Subject'] = 'e-Rugah SMTP Test - Connection Successful'
        
        body = """
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #ff6b35;">SMTP Connection Test Successful!</h2>
                <p>Your email settings are configured correctly.</p>
                <p><strong>Configuration Details:</strong></p>
                <ul>
                    <li>SMTP Host: {}</li>
                    <li>SMTP Port: {}</li>
                    <li>Encryption: {}</li>
                    <li>Email: {}</li>
                </ul>
                <p>You can now receive messages from your contact form.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">This is an automated test message from e-Rugah</p>
            </body>
        </html>
        """.format(smtp_host, smtp_port, smtp_encryption.upper(), gmail_user)
        
        msg.attach(MIMEText(body, 'html'))
        
        server.send_message(msg)
        server.quit()
        
        return jsonify({
            'success': True,
            'message': f'Connection successful! A test email has been sent to {gmail_user}'
        })
        
    except smtplib.SMTPAuthenticationError:
        return jsonify({
            'success': False,
            'message': 'Authentication failed. Please check your email and app password.'
        })
    except smtplib.SMTPConnectError:
        return jsonify({
            'success': False,
            'message': 'Could not connect to SMTP server. Please check host and port.'
        })
    except smtplib.SMTPException as e:
        return jsonify({
            'success': False,
            'message': f'SMTP error: {str(e)}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })

@app.route('/admin/mpesa-settings', methods=['GET', 'POST'])
@role_required('admin')
def admin_mpesa_settings():
    # Get or create M-Pesa config
    mpesa_config = MpesaConfig.query.first()
    if not mpesa_config:
        mpesa_config = MpesaConfig()
        db.session.add(mpesa_config)
        db.session.commit()
    
    if request.method == 'POST':
        # Update M-Pesa configuration
        mpesa_config.environment = request.form.get('environment', 'sandbox')
        mpesa_config.consumer_key = request.form.get('consumer_key', 'test_key')
        mpesa_config.consumer_secret = request.form.get('consumer_secret', 'test_secret')
        mpesa_config.shortcode = request.form.get('shortcode', '174379')
        mpesa_config.passkey = request.form.get('passkey', 'test_passkey')
        mpesa_config.callback_url = request.form.get('callback_url', 'https://yourapp.repl.co/mpesa/callback')
        mpesa_config.api_url = request.form.get('api_url', 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials')
        mpesa_config.stk_url = request.form.get('stk_url', 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest')
        mpesa_config.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('M-Pesa settings updated successfully!', 'success')
        return redirect(url_for('admin_mpesa_settings'))
    
    return render_template('admin_mpesa_settings.html', mpesa_config=mpesa_config)

@app.route('/admin/test-mpesa-connection', methods=['POST'])
@role_required('admin')
def test_mpesa_connection():
    """Test M-Pesa API connection"""
    import requests
    import base64
    
    try:
        data = request.get_json()
        consumer_key = data.get('consumer_key')
        consumer_secret = data.get('consumer_secret')
        api_url = data.get('api_url')
        
        credentials = base64.b64encode(f'{consumer_key}:{consumer_secret}'.encode()).decode()
        headers = {'Authorization': f'Basic {credentials}'}
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return jsonify({'success': True, 'message': 'Connection successful'})
        else:
            return jsonify({'success': False, 'message': f'API returned status {response.status_code}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/manage-chefs')
@role_required('admin')
def admin_manage_chefs():
    """Admin page to manage all chefs - view, delete, and manage ratings"""
    all_chefs = Chef.query.order_by(Chef.created_at.desc()).all()
    return render_template('admin_manage_chefs.html', chefs=all_chefs)

@app.route('/admin/chef/<int:chef_id>/delete', methods=['POST'])
@role_required('admin')
def admin_delete_chef(chef_id):
    """Delete a chef and their associated user account"""
    chef = Chef.query.get_or_404(chef_id)
    user = chef.user
    
    try:
        # Delete associated bookings first (if any)
        bookings = Booking.query.filter_by(chef_id=chef_id).all()
        for booking in bookings:
            # Delete payments associated with bookings
            Payment.query.filter_by(booking_id=booking.id).delete()
            db.session.delete(booking)
        
        # Delete the chef
        db.session.delete(chef)
        
        # Delete the user account
        db.session.delete(user)
        
        db.session.commit()
        flash(f'Chef {chef.name} and associated account deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting chef: {str(e)}', 'danger')
    
    return redirect(url_for('admin_manage_chefs'))

@app.route('/admin/chef/<int:chef_id>/add-rating', methods=['POST'])
@role_required('admin')
def admin_add_chef_rating(chef_id):
    """Add or update a chef's rating"""
    chef = Chef.query.get_or_404(chef_id)
    
    try:
        rating_value = int(request.form.get('rating_value'))
        
        if rating_value < 1 or rating_value > 5:
            flash('Rating must be between 1 and 5 stars', 'danger')
            return redirect(url_for('admin_manage_chefs'))
        
        # Add the rating to the chef's total
        chef.rating_total += rating_value
        chef.rating_count += 1
        
        db.session.commit()
        flash(f'Rating added successfully! {chef.name} now has an average rating of {chef.average_rating} stars', 'success')
    except ValueError:
        flash('Invalid rating value', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding rating: {str(e)}', 'danger')
    
    return redirect(url_for('admin_manage_chefs'))

@app.route('/admin/chef/<int:chef_id>/reset-rating', methods=['POST'])
@role_required('admin')
def admin_reset_chef_rating(chef_id):
    """Reset a chef's rating to zero"""
    chef = Chef.query.get_or_404(chef_id)
    
    try:
        chef.rating_total = 0
        chef.rating_count = 0
        
        db.session.commit()
        flash(f'Rating reset successfully for {chef.name}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting rating: {str(e)}', 'danger')
    
    return redirect(url_for('admin_manage_chefs'))

@app.route('/admin/images', methods=['GET', 'POST'])
@role_required('admin')
def admin_images():
    import os
    from werkzeug.utils import secure_filename

    sections = {
        'hero': {'folder': 'static/images/', 'url_prefix': 'images/'},
        'triangle': {'folder': 'static/hero-triangle/', 'url_prefix': 'hero-triangle/'},
        'chefs': {'folder': 'static/images/', 'url_prefix': 'images/'},  # expert chefs images
        'gallery': {'folder': 'static/images/', 'url_prefix': 'images/'},  # gallery images
        'products': {'folder': 'static/images/', 'url_prefix': 'images/'}  # if any
    }

    if request.method == 'POST':
        section = request.form.get('section')
        action = request.form.get('action')

        if section not in sections:
            flash('Invalid section', 'danger')
            return redirect(url_for('admin_images'))

        upload_folder = sections[section]['folder']

        if action == 'upload':
            files = request.files.getlist('files')
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(upload_folder, filename)
                    file.save(file_path)
            flash('Images uploaded successfully!', 'success')

        elif action == 'delete':
            filename = request.form.get('filename')
            if filename:
                file_path = os.path.join(upload_folder, secure_filename(filename))
                if os.path.exists(file_path):
                    os.remove(file_path)
                    flash('Image deleted successfully!', 'success')
                else:
                    flash('File not found', 'danger')

        elif action == 'replace':
            old_filename = request.form.get('old_filename')
            new_file = request.files.get('new_file')
            if old_filename and new_file:
                old_path = os.path.join(upload_folder, secure_filename(old_filename))
                if os.path.exists(old_path):
                    os.remove(old_path)
                filename = secure_filename(new_file.filename)
                new_path = os.path.join(upload_folder, filename)
                new_file.save(new_path)
                flash('Image replaced successfully!', 'success')

        return redirect(url_for('admin_images'))

    # GET: list images per section
    images = {}
    for sec, data in sections.items():
        folder = data['folder']
        url_prefix = data['url_prefix']
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
            images[sec] = {'files': files, 'url_prefix': url_prefix}
        else:
            images[sec] = {'files': [], 'url_prefix': url_prefix}

    return render_template('admin_images.html', images=images)

# Review Routes
@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    """Get all approved reviews"""
    reviews = Review.query.filter_by(is_approved=True).order_by(Review.created_at.desc()).all()
    return jsonify([{
        'id': r.id,
        'customer_name': r.customer_name,
        'event_type': r.event_type,
        'rating': r.rating,
        'review_text': r.review_text,
        'created_at': r.created_at.strftime('%Y-%m-%d')
    } for r in reviews])

@app.route('/api/reviews', methods=['POST'])
def submit_review():
    """Submit a new review"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not all(k in data for k in ['customer_name', 'event_type', 'rating', 'review_text']):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        # Validate rating
        rating = int(data['rating'])
        if rating < 1 or rating > 5:
            return jsonify({'success': False, 'message': 'Rating must be between 1 and 5'}), 400
        
        # Create new review
        review = Review(
            customer_name=data['customer_name'],
            event_type=data['event_type'],
            rating=rating,
            review_text=data['review_text'],
            is_approved=False  # Requires admin approval
        )
        
        db.session.add(review)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Thank you for your review! It will be published after admin approval.'
        })
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Failed to submit review: {e}")
        return jsonify({'success': False, 'message': 'Failed to submit review. Please try again.'}), 500

@app.route('/admin/reviews')
@role_required('admin')
def admin_reviews():
    """Admin page to manage reviews"""
    pending_reviews = Review.query.filter_by(is_approved=False).order_by(Review.created_at.desc()).all()
    approved_reviews = Review.query.filter_by(is_approved=True).order_by(Review.created_at.desc()).all()
    return render_template('admin_reviews.html', 
                         pending_reviews=pending_reviews,
                         approved_reviews=approved_reviews)

@app.route('/admin/reviews/<int:review_id>/approve', methods=['POST'])
@role_required('admin')
def approve_review(review_id):
    """Approve a review"""
    review = Review.query.get_or_404(review_id)
    review.is_approved = True
    db.session.commit()
    flash('Review approved successfully!', 'success')
    return redirect(url_for('admin_reviews'))

def _remove_review(review_id, success_message):
    """Shared helper for removing reviews."""
    review = Review.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    flash(success_message, 'success')
    return redirect(url_for('admin_reviews'))


@app.route('/admin/reviews/<int:review_id>/reject', methods=['POST'])
@role_required('admin')
def reject_review(review_id):
    """Reject a review and remove it from the system."""
    return _remove_review(review_id, 'Review rejected and removed.')


@app.route('/admin/reviews/<int:review_id>/delete', methods=['POST'])
@role_required('admin')
def delete_review(review_id):
    """Delete an approved review."""
    return _remove_review(review_id, 'Review deleted successfully!')

@app.route('/test-reviews')
def test_reviews():
    """Test page for reviews API"""
    return render_template('test_reviews.html')

# Admin Featured Chefs Routes
@app.route('/admin/featured-chefs')
@role_required('admin')
def admin_featured_chefs():
    """Admin page to manage featured chefs"""
    all_chefs = Chef.query.filter(
        Chef.is_verified.is_(True),
        Chef.is_approved.is_(True)
    ).order_by(
        Chef.is_featured.desc(),
        func.coalesce(Chef.featured_priority, 0).desc(),
        Chef.name
    ).all()
    return render_template('admin_featured_chefs.html', chefs=all_chefs)

@app.route('/admin/chefs/<int:chef_id>/toggle-featured', methods=['POST'])
@role_required('admin')
def toggle_chef_featured(chef_id):
    """Toggle chef featured status"""
    chef = Chef.query.get_or_404(chef_id)
    chef.is_featured = not chef.is_featured
    if not chef.is_featured:
        chef.featured_priority = 0
    db.session.commit()
    
    status = "featured" if chef.is_featured else "unfeatured"
    flash(f'Chef {chef.name} has been {status}!', 'success')
    return redirect(url_for('admin_featured_chefs'))

@app.route('/admin/chefs/<int:chef_id>/set-priority', methods=['POST'])
@role_required('admin')
def set_chef_priority(chef_id):
    """Set chef featured priority"""
    chef = Chef.query.get_or_404(chef_id)
    priority = int(request.form.get('priority', 0))
    chef.featured_priority = priority
    if priority > 0 and not chef.is_featured:
        chef.is_featured = True
    db.session.commit()
    flash(f'Priority for {chef.name} set to {priority}!', 'success')
    return redirect(url_for('admin_featured_chefs'))

# Chef Rating Routes
@app.route('/booking/<int:booking_id>/rate', methods=['POST'])
@role_required('customer')
def rate_chef(booking_id):
    """Submit a rating for a completed booking"""
    try:
        booking = Booking.query.get_or_404(booking_id)
        
        # Verify booking belongs to current user
        if booking.event.customer_id != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        # Verify booking is confirmed
        if booking.status != 'confirmed':
            return jsonify({'success': False, 'message': 'Can only rate confirmed bookings'}), 400
        
        # Verify event has passed
        if booking.event.event_date > datetime.utcnow():
            return jsonify({'success': False, 'message': 'Can only rate after event completion'}), 400
        
        # Verify not already rated
        if booking.rating_value is not None:
            return jsonify({'success': False, 'message': 'You have already rated this chef'}), 400
        
        data = request.get_json()
        rating_value = int(data.get('rating', 0))
        rating_comment = data.get('comment', '').strip()
        
        # Validate rating
        if rating_value < 1 or rating_value > 5:
            return jsonify({'success': False, 'message': 'Rating must be between 1 and 5'}), 400
        
        # Update booking with rating
        booking.rating_value = rating_value
        booking.rating_comment = rating_comment if rating_comment else None
        booking.rating_submitted_at = datetime.utcnow()
        
        # Update chef's rating aggregates
        chef = booking.chef
        if chef.rating_total is None:
            chef.rating_total = 0
        if chef.rating_count is None:
            chef.rating_count = 0
            
        chef.rating_total += rating_value
        chef.rating_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Thank you for rating your chef!',
            'new_average': chef.average_rating
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Failed to submit rating: {e}")
        return jsonify({'success': False, 'message': 'Failed to submit rating. Please try again.'}), 500

@app.route('/send-message', methods=['POST'])
@login_required
def send_message():
    """Send a message from logged-in user to admin email"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()
        
        # Validate inputs
        if not all([name, email, subject, message]):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        # Get email configuration from database
        email_configs = SystemConfig.query.filter(SystemConfig.key.in_([
            'gmail_user', 'gmail_password', 'smtp_host', 'smtp_port', 
            'smtp_encryption', 'admin_email', 'sender_name', 'email_timeout'
        ])).all()
        
        config_dict = {config.key: config.value for config in email_configs}
        
        gmail_user = config_dict.get('gmail_user')
        gmail_password = config_dict.get('gmail_password')
        smtp_host = config_dict.get('smtp_host', 'smtp.gmail.com')
        smtp_port = int(config_dict.get('smtp_port', 587))
        smtp_encryption = config_dict.get('smtp_encryption', 'tls')
        admin_email = config_dict.get('admin_email', gmail_user)
        sender_name = config_dict.get('sender_name', 'e-Rugah Contact Form')
        email_timeout = int(config_dict.get('email_timeout', 30))
        
        if not gmail_user or not gmail_password:
            return jsonify({
                'success': False, 
                'message': 'Email system not configured. Please contact administrator.'
            }), 500
        
        # Send email using SMTP
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import smtplib
        
        msg = MIMEMultipart('alternative')
        msg['From'] = f'{sender_name} <{gmail_user}>'
        msg['To'] = admin_email
        msg['Subject'] = f'e-Rugah Contact: {subject}'
        msg['Reply-To'] = email
        
        # Plain text version
        text_body = f"""
New Message from e-Rugah Contact Form

From: {name}
Email: {email}
Subject: {subject}

Message:
{message}

---
Sent via e-Rugah Contact Form
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        # HTML version
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <h2 style="color: #ff6b35; border-bottom: 3px solid #ff6b35; padding-bottom: 10px;">New Contact Form Message</h2>
                    
                    <div style="margin: 20px 0;">
                        <p style="margin: 10px 0;"><strong style="color: #333;">From:</strong> {name}</p>
                        <p style="margin: 10px 0;"><strong style="color: #333;">Email:</strong> <a href="mailto:{email}" style="color: #ff6b35;">{email}</a></p>
                        <p style="margin: 10px 0;"><strong style="color: #333;">Subject:</strong> {subject}</p>
                    </div>
                    
                    <div style="background-color: #fff8f5; padding: 20px; border-left: 4px solid #ff6b35; margin: 20px 0;">
                        <p style="margin: 0; color: #333; line-height: 1.6;">{message.replace(chr(10), '<br>')}</p>
                    </div>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    
                    <p style="color: #666; font-size: 12px; margin: 10px 0;">
                        Sent via e-Rugah Contact Form<br>
                        Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    </p>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email with configured settings
        if smtp_encryption == 'ssl':
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=email_timeout)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=email_timeout)
            if smtp_encryption == 'tls':
                server.starttls()
        
        server.login(gmail_user, gmail_password)
        server.send_message(msg)
        server.quit()
        
        return jsonify({
            'success': True, 
            'message': 'Your message has been sent successfully! We will get back to you soon.'
        })
        
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'message': 'Failed to send message. Please try again later.'
        }), 500

def init_db():
    with app.app_context():
        db.create_all()
        
        if not User.query.filter_by(email='admin@erugah.com').first():
            admin = User(email='admin@erugah.com', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
        
        if not SystemConfig.query.filter_by(key='deposit_percentage').first():
            config = SystemConfig(key='deposit_percentage', value='30')
            db.session.add(config)
        
        if MenuItem.query.count() == 0:
            sample_items = [
                MenuItem(name='Beef Stew', category='Main', price_per_person=500, ingredients='Beef, Onions, Tomatoes, Spices'),
                MenuItem(name='Chicken Curry', category='Main', price_per_person=450, ingredients='Chicken, Curry powder, Coconut milk'),
                MenuItem(name='Vegetable Rice', category='Side', price_per_person=200, ingredients='Rice, Mixed vegetables, Oil'),
                MenuItem(name='Chapati', category='Side', price_per_person=50, ingredients='Wheat flour, Oil, Salt'),
                MenuItem(name='Fruit Salad', category='Dessert', price_per_person=150, ingredients='Mixed fruits, Honey'),
            ]
            for item in sample_items:
                db.session.add(item)
        
        db.session.commit()
        print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
