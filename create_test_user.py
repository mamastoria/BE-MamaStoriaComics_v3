#!/usr/bin/env python
"""Create a test user for development/testing"""
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent dir to path
sys.path.insert(0, os.path.dirname(__file__))

from app.models.user import User
from app.core.database import Base
from app.core.config import settings
from app.services.auth_service import AuthService

def create_test_user():
    """Create a test user for development"""
    
    # Get database URL from settings
    db_url = settings.DATABASE_URL or "sqlite:///./test.db"
    print(f"Using database: {db_url}")
    
    # Create engine
    engine = create_engine(db_url)
    
    # Create tables if not exist
    Base.metadata.create_all(bind=engine)
    
    # Create session
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # Create tables if not exist
    Base.metadata.create_all(bind=engine)
    
    # Create session
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # Check if test user exists
        test_user = db.query(User).filter(User.phone_number == "+6287825785182").first()
        
        if test_user:
            print(f"Test user already exists: {test_user.phone_number}")
            return
        
        # Create test user
        user = AuthService.create_user(
            db=db,
            full_name="Test User",
            phone_number="+6287825785182",
            password="password123",
            email="test@mamastoria.com"
        )
        
        # Mark as verified
        user.is_verified = True
        db.commit()
        
        print(f"✅ Test user created successfully!")
        print(f"   Phone: +6287825785182")
        print(f"   Email: test@mamastoria.com")
        print(f"   Password: password123")
        
    except Exception as e:
        print(f"❌ Error creating test user: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()
    
    return True

if __name__ == "__main__":
    create_test_user()
