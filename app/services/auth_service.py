"""
Authentication Service
Handles user registration, login, OTP verification, and token management
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timedelta
from typing import Optional, Tuple
import random
import string

from app.models.user import User
from app.models.referral import Referral
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_verification_code
)
from app.core.config import settings


class AuthService:
    """Service for authentication operations"""
    
    @staticmethod
    def generate_referral_code() -> str:
        """Generate unique referral code: 2 random numbers + 2 random letters + 4 digits from timestamp"""
        # 2 random digits
        numbers = ''.join(random.choices(string.digits, k=2))

        # 2 random uppercase letters
        letters = ''.join(random.choices(string.ascii_uppercase, k=2))

        # 4 digits from current timestamp (last 4 digits of unix timestamp)
        import time
        timestamp = str(int(time.time()))[-4:]

        return numbers + letters + timestamp
    
    @staticmethod
    def create_user(
        db: Session,
        full_name: str,
        phone_number: str,
        password: str,
        email: Optional[str] = None,
        referral_code: Optional[str] = None
    ) -> User:
        """
        Create new user account
        
        Args:
            db: Database session
            full_name: User's full name
            phone_number: User's phone number (unique)
            password: Plain password (will be hashed)
            email: Optional email
            referral_code: Optional referral code from another user
            
        Returns:
            Created User object
        """
        # Generate unique referral code for this user
        while True:
            new_referral_code = AuthService.generate_referral_code()
            existing = db.query(User).filter(User.referral_code_id == new_referral_code).first()
            if not existing:
                break
        
        # Hash password
        try:
            hashed_password = get_password_hash(password)
        except Exception as e:
            # Debugging: Expose the actual length of the password being hashed
            raise ValueError(f"Password hashing failed. Password length: {len(password)}. First 5 chars: '{password[:5]}'. Original error: {str(e)}")
        
        # Generate verification code
        verification_code = generate_verification_code()
        
        # Validate referral code if provided
        referrer = None
        if referral_code:
            referrer = db.query(User).filter(User.referral_code_id == referral_code).first()
            if not referrer:
                # Invalid referral code - we'll still create the user but without referral
                referral_code = None

        # Create user
        user = User(
            full_name=full_name,
            phone_number=phone_number,
            email=email,
            password=hashed_password,
            referral_code_id=new_referral_code,
            referrals_for=referral_code,  # Code of person who referred them
            verification_code=verification_code,
            last_verification_sent_at=datetime.utcnow(),
            is_verified=False,
            kredit=0,
            balance=0,
            publish_quota=0
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        # Create referral record if valid referral code was provided
        if referrer and referral_code:
            referral_record = Referral(
                referrer_id=referrer.id_users,
                referred_user_id=user.id_users,
                referral_code=referral_code
            )
            db.add(referral_record)
            db.commit()

        # TODO: Send verification code via SMS/WhatsApp
        # For now, just log it
        print(f"Verification code for {phone_number}: {verification_code}")

        return user
    
    @staticmethod
    def authenticate_user(
        db: Session,
        identifier: str,
        password: str
    ) -> Optional[User]:
        """
        Authenticate user by email/phone and password
        
        Args:
            db: Database session
            identifier: Email or phone number
            password: Plain password
            
        Returns:
            User object if authenticated, None otherwise
        """
        # Find user by email or phone
        user = db.query(User).filter(
            or_(User.email == identifier, User.phone_number == identifier)
        ).first()
        
        if not user:
            return None
        
        # Verify password
        if not verify_password(password, user.password):
            return None
        
        return user
    
    @staticmethod
    def verify_otp(
        db: Session,
        phone_number: str,
        verification_code: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify OTP code
        
        Args:
            db: Database session
            phone_number: User's phone number
            verification_code: OTP code to verify
            
        Returns:
            Tuple of (success: bool, message: Optional[str])
        """
        user = db.query(User).filter(User.phone_number == phone_number).first()
        
        if not user:
            return False, "User not found"
        
        if user.is_verified:
            return False, "User already verified"
        
        if user.verification_code != verification_code:
            return False, "Invalid verification code"
        
        # Check if code expired (15 minutes)
        if user.last_verification_sent_at:
            expiry_time = user.last_verification_sent_at + timedelta(minutes=15)
            if datetime.utcnow() > expiry_time:
                return False, "Verification code expired"
        
        # Mark user as verified
        user.is_verified = True
        user.verification_code = None
        db.commit()
        
        return True, "User verified successfully"
    
    @staticmethod
    def resend_verification_code(
        db: Session,
        phone_number: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Resend verification code
        
        Args:
            db: Database session
            phone_number: User's phone number
            
        Returns:
            Tuple of (success: bool, message: Optional[str])
        """
        user = db.query(User).filter(User.phone_number == phone_number).first()
        
        if not user:
            return False, "User not found"
        
        if user.is_verified:
            return False, "User already verified"
        
        # Check rate limit (1 minute)
        if user.last_verification_sent_at:
            next_allowed = user.last_verification_sent_at + timedelta(minutes=1)
            if datetime.utcnow() < next_allowed:
                return False, "Please wait before requesting new code"
        
        # Generate new code
        new_code = generate_verification_code()
        user.verification_code = new_code
        user.last_verification_sent_at = datetime.utcnow()
        db.commit()
        
        # TODO: Send via SMS/WhatsApp
        print(f"New verification code for {phone_number}: {new_code}")
        
        return True, "Verification code sent"
    
    @staticmethod
    def create_tokens(user: User) -> dict:
        """
        Create access and refresh tokens for user
        
        Args:
            user: User object
            
        Returns:
            Dict with access_token, refresh_token, token_type, expires_in
        """
        access_token = create_access_token(data={"sub": user.id_users})
        refresh_token = create_refresh_token(data={"sub": user.id_users})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    
    @staticmethod
    def refresh_access_token(refresh_token: str) -> Optional[str]:
        """
        Create new access token from refresh token
        
        Args:
            refresh_token: Refresh token string
            
        Returns:
            New access token or None if invalid
        """
        payload = decode_token(refresh_token)
        
        if not payload or payload.get("type") != "refresh":
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # Create new access token
        new_access_token = create_access_token(data={"sub": user_id})
        return new_access_token
    
    @staticmethod
    def update_fcm_token(
        db: Session,
        user: User,
        fcm_token: str
    ) -> User:
        """
        Update user's FCM token for push notifications
        
        Args:
            db: Database session
            user: User object
            fcm_token: FCM token string
            
        Returns:
            Updated User object
        """
        user.fcm_token = fcm_token
        db.commit()
        db.refresh(user)
        return user
