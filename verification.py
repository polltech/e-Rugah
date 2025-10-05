import random
import string
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from models import db, VerificationCode, SystemConfig, PasswordResetCode

SMS_VERIFICATION_KEY = 'sms_verification_enabled'
SMS_VERIFICATION_DEFAULT = 'true'

def generate_verification_code(identifier, type):
    """Generate a 4-digit verification code for email or SMS"""
    code = ''.join(random.choices(string.digits, k=4))
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Delete any existing unused codes for this identifier and type
    existing = VerificationCode.query.filter_by(identifier=identifier, type=type, is_used=False).first()
    if existing:
        print(f"[DEBUG] Deleting existing code for {identifier}: {existing.code}")
        db.session.delete(existing)

    verification = VerificationCode(identifier=identifier, code=code, type=type, expires_at=expires_at)
    db.session.add(verification)
    db.session.commit()

    print(f"[DEBUG] Generated new code for {identifier}: {code}, expires at: {expires_at}")
    return code

def verify_code(identifier, code, type):
    """Verify the code for email or SMS"""
    print(f"[DEBUG] Verifying code: identifier={identifier}, code={code}, type={type}")
    
    verification = VerificationCode.query.filter_by(
        identifier=identifier,
        code=code,
        type=type,
        is_used=False
    ).first()

    if not verification:
        # Check if code exists but is used or wrong
        all_codes = VerificationCode.query.filter_by(identifier=identifier, type=type).all()
        print(f"[DEBUG] No matching unused code found. All codes for {identifier}: {[(c.code, c.is_used, c.expires_at) for c in all_codes]}")
        return False, "Invalid verification code"

    if datetime.utcnow() > verification.expires_at:
        print(f"[DEBUG] Code expired. Current time: {datetime.utcnow()}, Expires at: {verification.expires_at}")
        return False, "Verification code has expired"

    verification.is_used = True
    db.session.commit()
    
    print(f"[DEBUG] Code verified successfully")
    return True, "Code verified successfully"

def send_email_code(email):
    """Send 4-digit code via Gmail. Returns tuple (success, code)"""
    gmail_user = SystemConfig.query.filter_by(key='gmail_user').first()
    gmail_password = SystemConfig.query.filter_by(key='gmail_password').first()

    code = generate_verification_code(email, 'email')

    if not gmail_user or not gmail_password:
        print(f"[ERROR] Gmail credentials not configured. Please run setup_email.py to configure.")
        return (False, code)

    msg = MIMEMultipart()
    msg['From'] = gmail_user.value
    msg['To'] = email
    msg['Subject'] = 'e-Rugah Chef Registration - Email Verification'

    body = f"""
    Welcome to e-Rugah!

    Your email verification code is: {code}

    This code will expire in 10 minutes.

    If you didn't request this, please ignore this email.

    Best regards,
    e-Rugah Team
    """

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user.value, gmail_password.value)
        text = msg.as_string()
        server.sendmail(gmail_user.value, email, text)
        server.quit()
        print(f"[SUCCESS] Email sent to {email} with code: {code}")
        return (True, code)
    except Exception as e:
        print(f"[ERROR] Email sending failed: {e}. Code still generated: {code}")
        return (False, code)

def send_sms_code(phone):
    """Send 4-digit code via configured SMS provider. Returns tuple (success, code)"""
    # Get SMS provider configuration
    sms_provider = SystemConfig.query.filter_by(key='sms_provider').first()
    sms_api_key = SystemConfig.query.filter_by(key='sms_api_key').first()
    sms_api_secret = SystemConfig.query.filter_by(key='sms_api_secret').first()
    sms_sender_id = SystemConfig.query.filter_by(key='sms_sender_id').first()

    code = generate_verification_code(phone, 'sms')

    # Check if SMS credentials are configured
    if not sms_provider or not sms_api_key:
        print(f"[ERROR] SMS provider credentials not configured in admin settings.")
        return (False, code)

    provider = sms_provider.value.lower()
    message_text = f"e-Rugah Chef Registration - Your SMS verification code is: {code}. Expires in 10 minutes."

    try:
        if provider == 'twilio':
            success = send_sms_twilio(phone, message_text, sms_api_key.value, sms_api_secret.value if sms_api_secret else None, sms_sender_id.value if sms_sender_id else None)
        elif provider == 'africastalking':
            success = send_sms_africastalking(phone, message_text, sms_api_key.value, sms_sender_id.value if sms_sender_id else None)
        elif provider == 'nexmo' or provider == 'vonage':
            success = send_sms_nexmo(phone, message_text, sms_api_key.value, sms_api_secret.value if sms_api_secret else None, sms_sender_id.value if sms_sender_id else None)
        elif provider == 'messagebird':
            success = send_sms_messagebird(phone, message_text, sms_api_key.value, sms_sender_id.value if sms_sender_id else None)
        elif provider == 'custom':
            # For custom API integration
            print(f"[INFO] Custom SMS provider selected. Implement your custom SMS logic here.")
            success = False
        else:
            print(f"[ERROR] Unknown SMS provider: {provider}")
            success = False

        if success:
            print(f"[SUCCESS] SMS sent to {phone} with code: {code} via {provider}")
            return (True, code)
        else:
            print(f"[ERROR] SMS sending failed via {provider}. Code still generated: {code}")
            return (False, code)
    except Exception as e:
        print(f"[ERROR] SMS sending failed: {e}. Code still generated: {code}")
        import traceback
        traceback.print_exc()
        return (False, code)


def send_sms_twilio(phone, message, api_key, api_secret, sender_id):
    """Send SMS via Twilio"""
    try:
        from twilio.rest import Client
        client = Client(api_key, api_secret)
        message = client.messages.create(
            body=message,
            from_=sender_id,
            to=phone
        )
        return True
    except Exception as e:
        print(f"[ERROR] Twilio SMS failed: {e}")
        return False


def send_sms_africastalking(phone, message, api_key, sender_id):
    """Send SMS via Africa's Talking"""
    try:
        import africastalking
        # Initialize SDK
        africastalking.initialize(username='sandbox', api_key=api_key)  # Replace 'sandbox' with your username
        sms = africastalking.SMS
        
        response = sms.send(message, [phone], sender_id)
        return True
    except Exception as e:
        print(f"[ERROR] Africa's Talking SMS failed: {e}")
        return False


def send_sms_nexmo(phone, message, api_key, api_secret, sender_id):
    """Send SMS via Nexmo/Vonage"""
    try:
        url = "https://rest.nexmo.com/sms/json"
        payload = {
            'api_key': api_key,
            'api_secret': api_secret,
            'to': phone,
            'from': sender_id or 'e-Rugah',
            'text': message
        }
        response = requests.post(url, data=payload)
        result = response.json()
        
        if result['messages'][0]['status'] == '0':
            return True
        else:
            print(f"[ERROR] Nexmo error: {result['messages'][0]['error-text']}")
            return False
    except Exception as e:
        print(f"[ERROR] Nexmo SMS failed: {e}")
        return False


def send_sms_messagebird(phone, message, api_key, sender_id):
    """Send SMS via MessageBird"""
    try:
        url = "https://rest.messagebird.com/messages"
        headers = {
            'Authorization': f'AccessKey {api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'recipients': [phone],
            'originator': sender_id or 'e-Rugah',
            'body': message
        }
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 201:
            return True
        else:
            print(f"[ERROR] MessageBird error: {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] MessageBird SMS failed: {e}")
        return False


def is_sms_verification_enabled():
    """Check if SMS verification is enabled in system configuration."""
    config = SystemConfig.query.filter_by(key=SMS_VERIFICATION_KEY).first()
    if not config or config.value is None:
        return SMS_VERIFICATION_DEFAULT.lower() == 'true'
    return str(config.value).strip().lower() == 'true'


def generate_password_reset_code(email):
    """Generate a 6-digit password reset code"""
    code = ''.join(random.choices(string.digits, k=6))
    expires_at = datetime.utcnow() + timedelta(minutes=5)

    # Delete any existing unused codes for this email
    existing = PasswordResetCode.query.filter_by(email=email, is_used=False).all()
    for code_obj in existing:
        db.session.delete(code_obj)

    reset_code = PasswordResetCode(email=email, code=code, expires_at=expires_at)
    db.session.add(reset_code)
    db.session.commit()

    print(f"[DEBUG] Generated password reset code for {email}: {code}, expires at: {expires_at}")
    return code


def verify_password_reset_code(email, code):
    """Verify the password reset code"""
    print(f"[DEBUG] Verifying reset code: email={email}, code={code}")
    
    reset_code = PasswordResetCode.query.filter_by(
        email=email,
        code=code,
        is_used=False
    ).first()

    if not reset_code:
        print(f"[DEBUG] No matching unused reset code found")
        return False, "Invalid reset code"

    if datetime.utcnow() > reset_code.expires_at:
        print(f"[DEBUG] Reset code expired. Current time: {datetime.utcnow()}, Expires at: {reset_code.expires_at}")
        return False, "Reset code has expired"

    print(f"[DEBUG] Reset code verified successfully")
    return True, "Code verified successfully"


def mark_reset_code_used(email, code):
    """Mark the reset code as used"""
    reset_code = PasswordResetCode.query.filter_by(
        email=email,
        code=code,
        is_used=False
    ).first()
    
    if reset_code:
        reset_code.is_used = True
        db.session.commit()
        return True
    return False


def send_password_reset_email(email):
    """Send 6-digit password reset code via email. Returns tuple (success, code)"""
    gmail_user = SystemConfig.query.filter_by(key='gmail_user').first()
    gmail_password = SystemConfig.query.filter_by(key='gmail_password').first()

    code = generate_password_reset_code(email)

    if not gmail_user or not gmail_password:
        print(f"[ERROR] Gmail credentials not configured. Please run setup_email.py to configure.")
        return (False, code)

    msg = MIMEMultipart()
    msg['From'] = gmail_user.value
    msg['To'] = email
    msg['Subject'] = 'e-Rugah - Password Reset Code'

    body = f"""
    Hello,

    You requested to reset your password for your e-Rugah account.

    Your password reset code is: {code}

    This code will expire in 5 minutes.

    If you didn't request this password reset, please ignore this email and your password will remain unchanged.

    Best regards,
    e-Rugah Team
    """

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user.value, gmail_password.value)
        text = msg.as_string()
        server.sendmail(gmail_user.value, email, text)
        server.quit()
        print(f"[SUCCESS] Password reset email sent to {email} with code: {code}")
        return (True, code)
    except Exception as e:
        print(f"[ERROR] Email sending failed: {e}. Code still generated: {code}")
        return (False, code)