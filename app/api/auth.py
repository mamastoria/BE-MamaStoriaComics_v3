"""
Authentication API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.auth_service import AuthService
from app.services.google_oauth_service import GoogleOAuthService
from app.schemas.user import (
    UserRegister,
    UserLogin,
    UserVerify,
    ResendVerification,
    UpdateFCMToken,
    UserResponse,
    GoogleTokenVerify
)
from app.schemas.common import TokenResponse, MessageResponse
from app.models.user import User
from app.utils.responses import success_response, error_response

router = APIRouter()


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register new user account
    
    - **full_name**: User's full name
    - **phone_number**: User's phone number (unique)
    - **password**: Password (min 6 characters)
    - **email**: Optional email address
    - **referral_code**: Optional referral code from another user
    """
    # Check if phone number already exists
    existing_user = db.query(User).filter(User.phone_number == user_data.phone_number).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )
    
    # Check if email already exists (if provided)
    if user_data.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Create user
    try:
        user = AuthService.create_user(
            db=db,
            full_name=user_data.full_name,
            phone_number=user_data.phone_number,
            password=user_data.password,
            email=user_data.email,
            referral_code=user_data.referral_code
        )
        
        return {
            "ok": True,
            "message": "User registered successfully.",
            "data": {
                "user_id": user.id_users,
                "phone_number": user.phone_number,
                "verification_code_sent": False
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.post("/login", response_model=dict)
async def login(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Login with email/phone and password
    
    - **identifier**: Email or phone number
    - **password**: User password
    
    Returns JWT access token and refresh token
    """
    # Authenticate user
    user = AuthService.authenticate_user(
        db=db,
        identifier=credentials.identifier,
        password=credentials.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Check if user is verified
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your phone number first"
        )
    
    # Create tokens
    tokens = AuthService.create_tokens(user)
    
    return {
        "ok": True,
        "message": "Login successful",
        "data": {
            "user": UserResponse.model_validate(user).model_dump(),
            "tokens": tokens
        }
    }


@router.post("/verify", response_model=dict)
async def verify_otp(
    verify_data: UserVerify,
    db: Session = Depends(get_db)
):
    """
    Verify phone number with OTP code
    
    - **phone_number**: User's phone number
    - **verification_code**: 6-digit OTP code
    """
    success, message = AuthService.verify_otp(
        db=db,
        phone_number=verify_data.phone_number,
        verification_code=verify_data.verification_code
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Get user and create tokens
    user = db.query(User).filter(User.phone_number == verify_data.phone_number).first()
    tokens = AuthService.create_tokens(user)
    
    return {
        "ok": True,
        "message": message,
        "data": {
            "user": UserResponse.model_validate(user).model_dump(),
            "tokens": tokens
        }
    }


@router.post("/resend-verification", response_model=dict)
async def resend_verification(
    resend_data: ResendVerification,
    db: Session = Depends(get_db)
):
    """
    Resend verification code
    
    - **phone_number**: User's phone number
    """
    success, message = AuthService.resend_verification_code(
        db=db,
        phone_number=resend_data.phone_number
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return {
        "ok": True,
        "message": message
    }


@router.post("/refresh", response_model=dict)
async def refresh_token(
    refresh_token: str
):
    """
    Refresh access token using refresh token
    
    - **refresh_token**: Refresh token string
    """
    new_access_token = AuthService.refresh_access_token(refresh_token)
    
    if not new_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    return {
        "ok": True,
        "data": {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    }


@router.post("/logout", response_model=dict)
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout current user
    
    Note: In JWT-based auth, logout is typically handled client-side by removing the token.
    This endpoint is provided for consistency with the Laravel API.
    """
    return {
        "ok": True,
        "message": "Logged out successfully"
    }


@router.post("/user/update-fcm-token", response_model=dict)
async def update_fcm_token(
    fcm_data: UpdateFCMToken,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user's FCM token for push notifications
    
    - **fcm_token**: Firebase Cloud Messaging token
    """
    updated_user = AuthService.update_fcm_token(
        db=db,
        user=current_user,
        fcm_token=fcm_data.fcm_token
    )
    
    return {
        "ok": True,
        "message": "FCM token updated successfully"
    }


# ============ Google OAuth Endpoints ============

@router.get("/google/redirect")
async def google_oauth_redirect():
    """
    Redirect to Google OAuth consent screen
    
    This initiates the OAuth flow by redirecting the user to Google's
    authorization page. After authorization, Google will redirect back
    to the callback endpoint.
    """
    auth_url = GoogleOAuthService.get_google_auth_url()
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_oauth_callback(
    code: str,
    db: Session = Depends(get_db)
):
    """
    Handle Google OAuth callback
    
    This endpoint receives the authorization code from Google after
    the user authorizes the application. It exchanges the code for
    an access token and creates/logs in the user.
    
    - **code**: Authorization code from Google
    """
    # Exchange code for token
    token_data = await GoogleOAuthService.exchange_code_for_token(code)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange authorization code"
        )
    
    # Get user info from Google
    google_info = await GoogleOAuthService.get_user_info_from_token(
        token_data.get('access_token')
    )
    
    if not google_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get user information from Google"
        )
    
    # Get or create user
    user = GoogleOAuthService.get_or_create_user_from_google(
        db=db,
        google_info=google_info
    )
    
    # Create tokens
    tokens = AuthService.create_tokens(user)
    
    return {
        "ok": True,
        "message": "Google login successful",
        "data": {
            "user": UserResponse.model_validate(user).model_dump(),
            "tokens": tokens
        }
    }


@router.post("/google/verify-token", response_model=dict)
async def google_verify_token(
    token_data: GoogleTokenVerify,
    db: Session = Depends(get_db)
):
    """
    Verify Google ID token (for client-side OAuth)
    
    This endpoint is used when the client (mobile app or web) handles
    the OAuth flow and sends the ID token to the backend for verification.
    This is the recommended approach for mobile apps.
    
    - **id_token**: Google ID token from client
    """
    # Verify the Google token
    google_info = await GoogleOAuthService.verify_google_token(token_data.id_token)
    
    if not google_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )
    
    # Get or create user
    user = GoogleOAuthService.get_or_create_user_from_google(
        db=db,
        google_info=google_info
    )
    
    # Create tokens
    tokens = AuthService.create_tokens(user)
    
    return {
        "ok": True,
        "message": "Google login successful",
        "data": {
            "user": UserResponse.model_validate(user).model_dump(),
            "tokens": tokens
        }
    }
