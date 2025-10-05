"""
Initialize M-Pesa Configuration Table
This script creates the mpesa_config table and adds default configuration
"""

from main import app, db
from models import MpesaConfig

def init_mpesa_config():
    with app.app_context():
        # Create the table
        db.create_all()
        
        # Check if config already exists
        existing_config = MpesaConfig.query.first()
        
        if not existing_config:
            # Create default configuration
            default_config = MpesaConfig(
                environment='sandbox',
                consumer_key='test_key',
                consumer_secret='test_secret',
                shortcode='174379',
                passkey='test_passkey',
                callback_url='https://yourapp.repl.co/mpesa/callback',
                api_url='https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
                stk_url='https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
            )
            db.session.add(default_config)
            db.session.commit()
            print("✅ M-Pesa configuration table created with default values")
            print("📝 Please update the configuration in Admin Dashboard > M-Pesa Settings")
        else:
            print("✅ M-Pesa configuration already exists")
            print(f"   Environment: {existing_config.environment}")
            print(f"   Shortcode: {existing_config.shortcode}")

if __name__ == '__main__':
    init_mpesa_config()