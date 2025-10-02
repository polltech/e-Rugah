from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from functools import wraps
import os
import json
import csv
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from models import db, User, Chef, Event, MenuItem, Booking, Payment, OTP, SystemConfig
from payments import initiate_mpesa_stk, handle_mpesa_callback
from otp import generate_otp, verify_otp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SESSION_SECRET', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erugah.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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
    if current_user.is_authenticated:
        return render_template('index.html')
    else:
        return render_template('welcome.html')

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
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
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

@app.route('/customer/dashboard')
@role_required('customer')
def customer_dashboard():
    events = Event.query.filter_by(customer_id=current_user.id).all()
    return render_template('customer_dashboard.html', events=events)

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
        menu_items = request.form.getlist('menu_items')
        
        event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
        total_guests = adult_guests + child_guests
        
        selected_items = MenuItem.query.filter(MenuItem.id.in_(menu_items)).all()
        total_cost = sum(item.price_per_person * total_guests for item in selected_items)
        
        event = Event(
            customer_id=current_user.id,
            county=county,
            sub_county=sub_county,
            town=town,
            adult_guests=adult_guests,
            child_guests=child_guests,
            event_date=event_date,
            menu_items=','.join(menu_items),
            total_cost=total_cost
        )
        db.session.add(event)
        db.session.commit()
        
        flash('Event created successfully!', 'success')
        return redirect(url_for('match_chefs', event_id=event.id))
    
    menu_items = MenuItem.query.all()
    return render_template('create_event.html', menu_items=menu_items)

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
            flash('Maximum 5 meals allowed', 'danger')
            return redirect(url_for('chef_register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('chef_register'))
        
        user = User(email=email, role='chef')
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        
        chef = Chef(
            user_id=user.id,
            name=name,
            phone=phone,
            county=county,
            sub_county=sub_county,
            town=town,
            about=about,
            meals_offered=','.join(meals),
            is_verified=False,
            is_approved=False
        )
        db.session.add(chef)
        db.session.commit()
        
        otp_code = generate_otp(email)
        
        flash('Registration successful! Please verify your email with the OTP sent.', 'success')
        return redirect(url_for('verify_otp_page', email=email))
    
    return render_template('chef_register.html')

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
                flash('Email verified successfully! Admin approval pending.', 'success')
                return redirect(url_for('login'))
        
        flash(message, 'danger')
    
    return render_template('verify_otp.html', email=email)

@app.route('/chef/dashboard')
@role_required('chef')
def chef_dashboard():
    chef = Chef.query.filter_by(user_id=current_user.id).first()
    if not chef:
        flash('Chef profile not found', 'danger')
        return redirect(url_for('index'))
    
    bookings = Booking.query.filter_by(chef_id=chef.id).all()
    return render_template('chef_dashboard.html', chef=chef, bookings=bookings)

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

@app.route('/admin/chef/<int:chef_id>/approve')
@role_required('admin')
def approve_chef(chef_id):
    chef = Chef.query.get_or_404(chef_id)
    chef.is_approved = True
    db.session.commit()
    flash(f'Chef {chef.name} approved successfully!', 'success')
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
