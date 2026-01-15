"""
Script to create admin user directly via database
Run this once to create initial admin account
"""
import os
import sys
from sqlalchemy import create_engine, text
import bcrypt

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+pg8000://postgres:your_password@/nanobanana_db?unix_sock=/cloudsql/nanobananacomic-482111:asia-southeast2:cloudsql-nanobanana-dev/.s.PGSQL.5432")

engine = create_engine(DATABASE_URL)

# Admin credentials
PHONE = "+6281234567890"
PASSWORD = "admin123"
FULL_NAME = "Admin Dashboard"
KREDIT = 999999

# Hash password
password_hash = bcrypt.hashpw(PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Generate referral code
import secrets
referral_code = secrets.token_hex(4).upper()

try:
    with engine.connect() as conn:
        # Check if user exists
        result = conn.execute(
            text("SELECT id_users, role FROM users WHERE phone_number = :phone"),
            {"phone": PHONE}
        ).fetchone()
        
        if result:
            user_id, current_role = result
            print(f"User exists (ID: {user_id}, Role: {current_role})")
            
            # Update to admin role
            conn.execute(
                text("UPDATE users SET role = 'admin', kredit = :kredit WHERE id_users = :id"),
                {"kredit": KREDIT, "id": user_id}
            )
            conn.commit()
            print(f"✅ User {PHONE} updated to admin role with {KREDIT} credits")
        else:
            # Create new admin user
            conn.execute(
                text("""
                    INSERT INTO users (
                        phone_number, password, full_name, kredit, 
                        is_verified, referral_code_id, role
                    ) VALUES (
                        :phone, :password, :full_name, :kredit,
                        true, :referral_code, 'admin'
                    )
                """),
                {
                    "phone": PHONE,
                    "password": password_hash,
                    "full_name": FULL_NAME,
                    "kredit": KREDIT,
                    "referral_code": referral_code
                }
            )
            conn.commit()
            print(f"✅ Admin user created successfully!")
            print(f"   Phone: {PHONE}")
            print(f"   Password: {PASSWORD}")
            print(f"   Credits: {KREDIT}")
            
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
