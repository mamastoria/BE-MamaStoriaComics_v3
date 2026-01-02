"""
Google OAuth Service
Handles Google OAuth authentication and token verification
"""
from google.oauth2 import id_token
from google.auth.transport import requests
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import httpx

from app.models.user import User
from app.core.config import settings
from app.core.security import generate_verification_code
from app.services.auth_service import AuthService


class GoogleOAuthService:
    """Service for Google OAuth operations"""
    
    @staticmethod
    async def verify_google_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify Google ID token or Access Token
        """
        # 1. Try as JWT ID Token
        try:
            idinfo = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )
            
            if idinfo['iss'] in ['accounts.google.com', 'https://accounts.google.com']:
                return {
                    'email': idinfo.get('email'),
                    'email_verified': idinfo.get('email_verified', False),
                    'name': idinfo.get('name'),
                    'picture': idinfo.get('picture'),
                    'google_id': idinfo.get('sub')
                }
        except Exception:
            pass

        # 2. Try as Access Token (fallback)
        try:
            # Use the existing method to fetch profile via UserInfo endpoint
            user_info = await GoogleOAuthService.get_user_info_from_token(token)
            if user_info:
                return user_info
        except Exception as e:
            print(f"Error checking token as Access Token: {str(e)}")

        return None
    
    @staticmethod
    def get_or_create_user_from_google(
        db: Session,
        google_info: Dict[str, Any]
    ) -> User:
        """
        Get existing user or create new user from Google info
        
        Args:
            db: Database session
            google_info: User info from Google
            
        Returns:
            User object
        """
        # Check if user exists by external_id (Google ID)
        user = db.query(User).filter(User.external_id == google_info['google_id']).first()
        
        if user:
            # Update user info if needed
            if google_info.get('picture') and not user.profile_photo_path:
                user.profile_photo_path = google_info['picture']
            
            # Trust Google verification and auto-verify user
            if google_info.get('email_verified') and not user.is_verified:
                user.is_verified = True
                user.verification_code = None
                
            db.commit()
            db.refresh(user)
            return user
        
        # Check if user exists by email
        if google_info.get('email'):
            user = db.query(User).filter(User.email == google_info['email']).first()
            if user:
                # Link Google account to existing user
                user.external_id = google_info['google_id']
                user.login_method = 'google'
                if google_info.get('picture') and not user.profile_photo_path:
                    user.profile_photo_path = google_info['picture']

                # Trust Google verification and auto-verify user
                if google_info.get('email_verified') and not user.is_verified:
                    user.is_verified = True
                    user.verification_code = None

                db.commit()
                db.refresh(user)
                return user
        
        # Create new user
        # Generate a phone number placeholder (will need to be updated later)
        phone_number = f"google_{google_info['google_id'][:10]}"
        
        user = User(
            full_name=google_info.get('name', 'Google User'),
            email=google_info.get('email'),
            phone_number=phone_number,
            password='',  # No password for Google OAuth users
            external_id=google_info['google_id'],
            login_method='google',
            is_verified=google_info.get('email_verified', True),  # Trust Google verification
            referral_code_id=AuthService.generate_referral_code(),
            profile_photo_path=google_info.get('picture'),
            role='user',
            kredit=0,
            balance=0,
            publish_quota=5  # Default quota
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def get_google_auth_url(state: str = "") -> str:
        """
        Generate Google OAuth authorization URL
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL
        """
        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "state": state
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{base_url}?{query_string}"
    
    @staticmethod
    async def exchange_code_for_token(code: str) -> Optional[Dict[str, Any]]:
        """
        Exchange authorization code for access token
        
        Args:
            code: Authorization code from Google
            
        Returns:
            Token info dict if successful, None otherwise
        """
        token_url = "https://oauth2.googleapis.com/token"
        
        data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Error exchanging code: {response.text}")
                    return None
        except Exception as e:
            print(f"Error exchanging code for token: {str(e)}")
            return None
    
    @staticmethod
    async def get_user_info_from_token(access_token: str) -> Optional[Dict[str, Any]]:
        """
        Get user info from Google using access token
        
        Args:
            access_token: Google access token
            
        Returns:
            User info dict if successful, None otherwise
        """
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    info = response.json()
                    return {
                        'email': info.get('email'),
                        'email_verified': info.get('verified_email', False),
                        'name': info.get('name'),
                        'picture': info.get('picture'),
                        'google_id': info.get('id')
                    }
                else:
                    print(f"Error getting user info: {response.text}")
                    return None
        except Exception as e:
            print(f"Error getting user info: {str(e)}")
            return None
