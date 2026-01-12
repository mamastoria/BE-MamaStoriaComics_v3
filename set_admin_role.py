
import sys
import os
from pathlib import Path

# Add root directory to python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import get_db, get_session_local
from app.models.user import User
from sqlalchemy import text

def set_admin(phone_number):
    try:
        SessionLocal = get_session_local()
        db = SessionLocal()
        user = db.query(User).filter(User.phone_number == phone_number).first()
        
        if not user:
            print(f"User with phone {phone_number} not found!")
            return False
            
        print(f"Found user: {user.full_name} (ID: {user.id_users})")
        print(f"Current role: {user.role}")
        
        user.role = 'admin'
        db.commit()
        
        print(f"Successfully updated role to 'admin' for user {phone_number}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    # Gunakan nomor HP dari request user
    phone = "081234567890"
    set_admin(phone)
