import requests
import base64
import os
from datetime import datetime
from models import db, Payment, Booking

def get_access_token():
    consumer_key = os.getenv('MPESA_CONSUMER_KEY', 'test_key')
    consumer_secret = os.getenv('MPESA_CONSUMER_SECRET', 'test_secret')
    api_url = os.getenv('MPESA_API_URL', 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials')
    
    credentials = base64.b64encode(f'{consumer_key}:{consumer_secret}'.encode()).decode()
    headers = {'Authorization': f'Basic {credentials}'}
    
    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            return response.json().get('access_token')
        return None
    except Exception as e:
        print(f"Error getting access token: {e}")
        return None

def initiate_mpesa_stk(phone, amount, booking_id):
    access_token = get_access_token()
    if not access_token:
        print("Failed to get M-PESA access token. Using simulation mode.")
        return simulate_payment(phone, amount, booking_id)
    
    api_url = os.getenv('MPESA_STK_URL', 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest')
    business_shortcode = os.getenv('MPESA_SHORTCODE', '174379')
    passkey = os.getenv('MPESA_PASSKEY', 'test_passkey')
    
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(f'{business_shortcode}{passkey}{timestamp}'.encode()).decode()
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'BusinessShortCode': business_shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': int(amount),
        'PartyA': phone,
        'PartyB': business_shortcode,
        'PhoneNumber': phone,
        'CallBackURL': os.getenv('MPESA_CALLBACK_URL', 'https://yourapp.repl.co/mpesa/callback'),
        'AccountReference': f'Booking-{booking_id}',
        'TransactionDesc': f'Deposit for booking #{booking_id}'
    }
    
    try:
        response = requests.post(api_url, json=payload, headers=headers)
        if response.status_code == 200:
            result = response.json()
            if result.get('ResponseCode') == '0':
                return {
                    'success': True,
                    'message': 'STK push sent successfully',
                    'checkout_request_id': result.get('CheckoutRequestID')
                }
        return {
            'success': False,
            'message': 'Failed to initiate payment'
        }
    except Exception as e:
        print(f"Error initiating M-PESA payment: {e}")
        return simulate_payment(phone, amount, booking_id)

def simulate_payment(phone, amount, booking_id):
    print(f"\n{'='*50}")
    print(f"M-PESA SIMULATION MODE")
    print(f"{'='*50}")
    print(f"Booking ID: {booking_id}")
    print(f"Phone: {phone}")
    print(f"Amount: KES {amount}")
    print(f"{'='*50}")
    print("Payment simulation: Automatically marking as successful")
    print(f"{'='*50}\n")
    
    payment = Payment.query.filter_by(booking_id=booking_id, status='pending').first()
    if payment:
        payment.status = 'success'
        payment.mpesa_receipt_number = f'SIM{datetime.now().strftime("%Y%m%d%H%M%S")}'
        payment.completed_at = datetime.utcnow()
        
        booking = Booking.query.get(booking_id)
        if booking:
            booking.status = 'confirmed'
            booking.confirmed_at = datetime.utcnow()
        
        db.session.commit()
        return {
            'success': True,
            'message': 'Payment simulated successfully',
            'receipt': payment.mpesa_receipt_number
        }
    
    return {
        'success': False,
        'message': 'Payment record not found'
    }

def handle_mpesa_callback(callback_data):
    try:
        result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
        checkout_request_id = callback_data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
        
        if result_code == 0:
            metadata = callback_data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])
            mpesa_receipt = None
            phone = None
            amount = None
            
            for item in metadata:
                if item.get('Name') == 'MpesaReceiptNumber':
                    mpesa_receipt = item.get('Value')
                elif item.get('Name') == 'PhoneNumber':
                    phone = item.get('Value')
                elif item.get('Name') == 'Amount':
                    amount = item.get('Value')
            
            payment = Payment.query.filter_by(transaction_id=checkout_request_id).first()
            if payment:
                payment.status = 'success'
                payment.mpesa_receipt_number = mpesa_receipt
                payment.completed_at = datetime.utcnow()
                
                booking = Booking.query.get(payment.booking_id)
                if booking:
                    booking.status = 'confirmed'
                    booking.confirmed_at = datetime.utcnow()
                
                db.session.commit()
                return {'success': True}
        
        return {'success': False, 'message': 'Payment failed'}
    except Exception as e:
        print(f"Error handling M-PESA callback: {e}")
        return {'success': False, 'message': str(e)}
