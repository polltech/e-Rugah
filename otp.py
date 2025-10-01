import random
import string
from datetime import datetime, timedelta
from models import db, OTP

def generate_otp(email):
    code = ''.join(random.choices(string.digits, k=6))
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    
    existing_otp = OTP.query.filter_by(email=email, is_used=False).first()
    if existing_otp:
        db.session.delete(existing_otp)
    
    otp = OTP(email=email, code=code, expires_at=expires_at)
    db.session.add(otp)
    db.session.commit()
    
    print(f"\n{'='*50}")
    print(f"OTP VERIFICATION CODE")
    print(f"{'='*50}")
    print(f"Email: {email}")
    print(f"Code: {code}")
    print(f"Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*50}\n")
    
    return code

def verify_otp(email, code):
    otp = OTP.query.filter_by(email=email, code=code, is_used=False).first()
    
    if not otp:
        return False, "Invalid OTP code"
    
    if datetime.utcnow() > otp.expires_at:
        return False, "OTP code has expired"
    
    otp.is_used = True
    db.session.commit()
    
    return True, "OTP verified successfully"
