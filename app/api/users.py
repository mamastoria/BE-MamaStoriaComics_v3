"""
User Management API endpoints
Profile, password management, credits, etc.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import verify_password, get_password_hash, generate_verification_code
from app.models.user import User
from app.schemas.user import (
    UserResponse,
    UpdateProfile,
    ChangePassword,
    SendResetToken,
    VerifyResetToken,
    ResetPassword,
    CheckVerificationCode,
    SendOTP,
    UpdateKredit,
    ProfileRating,
    ProfileRating,
    ReferralCodeResponse,
    UpdateWatermark
)
from app.services.google_storage_service import GoogleStorageService
from datetime import datetime, timedelta
import uuid

router = APIRouter()


@router.get("/profile", response_model=dict)
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user profile
    
    Returns complete user information including credits, balance, quota, etc.
    """
    return {
        "ok": True,
        "data": UserResponse.model_validate(current_user).model_dump()
    }


@router.post("/profile/update-details", response_model=dict)
async def update_profile_details(
    profile_data: UpdateProfile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user profile details (name, username, email)
    
    - **full_name**: New full name (optional)
    - **username**: New username (optional, must be unique)
    - **email**: New email (optional, must be unique)
    """
    # Check username uniqueness if provided
    if profile_data.username:
        existing = db.query(User).filter(
            User.username == profile_data.username,
            User.id_users != current_user.id_users
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        current_user.username = profile_data.username
    
    # Check email uniqueness if provided
    if profile_data.email:
        existing = db.query(User).filter(
            User.email == profile_data.email,
            User.id_users != current_user.id_users
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        current_user.email = profile_data.email
    
    # Update full name if provided
    if profile_data.full_name:
        current_user.full_name = profile_data.full_name
    
    db.commit()
    db.refresh(current_user)
    
    return {
        "ok": True,
        "message": "Profile updated successfully",
        "data": UserResponse.model_validate(current_user).model_dump()
    }


@router.post("/profile/update-photo", response_model=dict)
async def update_profile_photo(
    photo: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload and update user profile photo
    
    - **photo**: Image file (jpg, jpeg, png, webp)
    """
    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if photo.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only JPEG, PNG, and WebP are allowed."
        )
    
    # Read file content
    file_content = await photo.read()
    
    # Generate unique filename
    file_extension = photo.filename.split(".")[-1]
    filename = f"profiles/{current_user.id_users}_{uuid.uuid4()}.{file_extension}"
    
    # Upload to GCS
    try:
        storage_service = GoogleStorageService()
        photo_url = storage_service.upload_file(
            file_content=file_content,
            destination_path=filename,
            content_type=photo.content_type,
            make_public=True
        )
        
        # Update user profile
        current_user.profile_photo_path = photo_url
        db.commit()
        db.refresh(current_user)
        
        return {
            "ok": True,
            "message": "Profile photo updated successfully",
            "data": {
                "profile_photo_url": photo_url
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload photo: {str(e)}"
        )


@router.post("/profile/update-watermark", response_model=dict)
async def update_watermark(
    watermark_data: UpdateWatermark,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update watermark preference
    
    - **watermark**: boolean (true/false)
    """
    current_user.watermark = watermark_data.watermark
    db.commit()
    db.refresh(current_user)
    
    return {
        "ok": True,
        "message": "Watermark preference updated successfully",
        "data": {
            "watermark": current_user.watermark
        }
    }


@router.post("/password/change-password", response_model=dict)
async def change_password(
    password_data: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user password
    
    - **old_password**: Current password
    - **new_password**: New password (min 6 characters)
    """
    # Verify old password
    if not verify_password(password_data.old_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Update password
    current_user.password = get_password_hash(password_data.new_password)
    db.commit()
    
    return {
        "ok": True,
        "message": "Password changed successfully"
    }


@router.post("/password/send-reset-token", response_model=dict)
async def send_reset_token(
    reset_data: SendResetToken,
    db: Session = Depends(get_db)
):
    """
    Send password reset token via Email
    
    - **email**: User's email address
    """
    user = db.query(User).filter(User.email == reset_data.email).first()
    
    if not user:
        # Don't reveal if user exists or not (security)
        return {
            "ok": True,
            "message": "If the email is registered, a reset code will be sent."
        }
    
    # Generate reset token (6 digits)
    reset_token = generate_verification_code()
    
    # Store in verification_code field (reusing OTP field)
    user.verification_code = reset_token
    user.last_verification_sent_at = datetime.utcnow()
    db.commit()
    
    # Send email via Resend
    try:
        import requests
        
        RESEND_KEY = "re_hsvmU2Zv_EjdhcaWUC7aRuUgfjfinhfVq"
        RESEND_URL = "https://api.resend.com/emails"
        RESEND_EMAIL_FROM = "onboarding@resend.dev"
        
        headers = {
            "Authorization": f"Bearer {RESEND_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "from": RESEND_EMAIL_FROM,
            "to": [reset_data.email],
            "subject": "Password Reset Code",
            "html": f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2>Password Reset Request</h2>
                    <p>You have requested to reset your password. Use the code below:</p>
                    <h1 style="background-color: #f0f0f0; padding: 20px; text-align: center; letter-spacing: 5px;">
                        {reset_token}
                    </h1>
                    <p>This code will expire in 15 minutes.</p>
                    <p>If you didn't request this, please ignore this email and your password will remain unchanged.</p>
                </div>
            """
        }
        
        response = requests.post(RESEND_URL, json=payload, headers=headers)
        response.raise_for_status()
        
        print(f"Password reset code sent to {reset_data.email}: {reset_token}")
        
    except Exception as e:
        # Log error but don't fail the request (security)
        print(f"Failed to send reset email: {str(e)}")
        # Still return success message to not reveal if email exists
    
    return {
        "ok": True,
        "message": "Reset code sent successfully to your email"
    }


@router.post("/password/verify-reset-token", response_model=dict)
async def verify_reset_token(
    verify_data: VerifyResetToken,
    db: Session = Depends(get_db)
):
    """
    Verify password reset token
    
    - **email**: User's email address
    - **reset_token**: 6-digit reset code
    """
    user = db.query(User).filter(User.email == verify_data.email).first()
    
    if not user or user.verification_code != verify_data.reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset code"
        )
    
    # Check expiry (15 minutes)
    if user.last_verification_sent_at:
        expiry = user.last_verification_sent_at + timedelta(minutes=15)
        if datetime.utcnow() > expiry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset code expired"
            )
    
    return {
        "ok": True,
        "message": "Reset code verified. You can now reset your password."
    }


@router.post("/password/reset-password", response_model=dict)
async def reset_password(
    reset_data: ResetPassword,
    db: Session = Depends(get_db)
):
    """
    Reset password with verified token
    
    - **email**: User's email address
    - **reset_token**: Verified reset code
    - **new_password**: New password (min 6 characters)
    """
    user = db.query(User).filter(User.email == reset_data.email).first()
    
    if not user or user.verification_code != reset_data.reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset code"
        )
    
    # Check expiry
    if user.last_verification_sent_at:
        expiry = user.last_verification_sent_at + timedelta(minutes=15)
        if datetime.utcnow() > expiry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset code expired"
            )
    
    # Update password
    user.password = get_password_hash(reset_data.new_password)
    user.verification_code = None  # Clear reset token
    db.commit()
    
    return {
        "ok": True,
        "message": "Password reset successfully"
    }


@router.post("/users/check-verification-code", response_model=dict)
async def check_verification_code(
    check_data: CheckVerificationCode,
    db: Session = Depends(get_db)
):
    """
    Check if verification code is valid for a given email
    
    - **email**: User's email address
    - **verification_code**: 6-digit verification code
    
    Returns user info if code is valid and not expired
    """
    user = db.query(User).filter(User.email == check_data.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.verification_code != check_data.verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )
    
    # Check expiry (15 minutes)
    if user.last_verification_sent_at:
        expiry = user.last_verification_sent_at + timedelta(minutes=15)
        if datetime.utcnow() > expiry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code expired"
            )
    
    return {
        "ok": True,
        "message": "Verification code is valid",
        "data": {
            "user_id": user.id_users,
            "email": user.email,
            "full_name": user.full_name,
            "is_verified": user.is_verified
        }
    }


@router.post("/users/send-otp", response_model=dict)
async def send_otp(
    otp_data: SendOTP,
    db: Session = Depends(get_db)
):
    """
    Send OTP verification code to email
    
    - **email**: User's email address
    
    Generates 6-digit OTP, saves to database, and sends via email
    Returns simple true/false response
    """
    # Check if user exists
    user = db.query(User).filter(User.email == otp_data.email).first()
    
    if not user:
        # Return false without revealing user doesn't exist (security)
        # Modified for debugging: return clearer message
        print(f"Send OTP failed - User not found: {otp_data.email}")
        return {
            "ok": False,
            "message": "User not found"
        }
    
    # Generate 6-digit OTP
    otp_code = generate_verification_code()
    
    # Save to database
    user.verification_code = otp_code
    user.last_verification_sent_at = datetime.utcnow()
    db.commit()
    
    # Send email via Resend
    try:
        import requests
        
        RESEND_KEY = "re_hsvmU2Zv_EjdhcaWUC7aRuUgfjfinhfVq"
        RESEND_URL = "https://api.resend.com/emails"
        RESEND_EMAIL_FROM = "onboarding@resend.dev"
        
        headers = {
            "Authorization": f"Bearer {RESEND_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "from": RESEND_EMAIL_FROM,
            "to": [otp_data.email],
            "subject": "Your Verification Code",
            "html": f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2>Verification Code</h2>
                    <p>Your verification code is:</p>
                    <h1 style="background-color: #f0f0f0; padding: 20px; text-align: center; letter-spacing: 5px;">
                        {otp_code}
                    </h1>
                    <p>This code will expire in 15 minutes.</p>
                    <p>If you didn't request this code, please ignore this email.</p>
                </div>
            """
        }
        
        response = requests.post(RESEND_URL, json=payload, headers=headers)
        response.raise_for_status()
        
        return {"ok": True}
        
    except Exception as e:
        # Log error but still return false (don't expose internal errors)
        print(f"Failed to send OTP email: {str(e)}")
        return {
            "ok": False, 
            "message": f"Failed to send email: {str(e)}"
        }


@router.post("/profile/update-kredit", response_model=dict)
async def update_kredit(
    kredit_data: UpdateKredit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user credits (add or subtract)
    
    - **amount**: Amount to add/subtract
    - **operation**: "add" or "subtract"
    """
    # Refetch user to ensure we have the latest data and lock the row
    user = db.query(User).filter(User.id_users == current_user.id_users).with_for_update().first()
    
    if not user:
         raise HTTPException(status_code=404, detail="User not found")

    if kredit_data.operation == "add":
        user.kredit += kredit_data.amount
    elif kredit_data.operation == "subtract":
        if user.kredit < kredit_data.amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient credits"
            )
        user.kredit -= kredit_data.amount
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid operation. Use 'add' or 'subtract'"
        )
    
    # Optional: Log to Transaction table if you have one
    # from app.models.subscription import Transaction
    # transaction = Transaction(
    #    user_id=user.id_users,
    #    type="credit_update",
    #    amount=kredit_data.amount if kredit_data.operation == "add" else -kredit_data.amount,
    #    description=kredit_data.description or f"Manual credit {kredit_data.operation}"
    # )
    # db.add(transaction)
    
    db.add(user) # Mark as modified
    db.commit()
    db.refresh(user)
    
    return {
        "ok": True,
        "message": f"Credits {kredit_data.operation}ed successfully",
        "data": {
            "current_kredit": user.kredit
        }
    }


@router.get("/profile/referral-code", response_model=dict)
async def get_referral_code(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's referral code and statistics
    
    Returns referral code, total referrals, and total bonus earned
    """
    # Count referrals
    total_referrals = db.query(User).filter(
        User.referrals_for == current_user.referral_code_id
    ).count()
    
    # TODO: Calculate total bonus from referrals table
    total_bonus = 0
    
    return {
        "ok": True,
        "data": {
            "referral_code": current_user.referral_code_id,
            "total_referrals": total_referrals,
            "total_bonus_earned": total_bonus
        }
    }


@router.get("/profile/rating", response_model=dict)
async def get_profile_rating(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's profile rating and statistics
    
    Returns rating, total comics, views, and likes
    """
    from app.models.comic import Comic
    from sqlalchemy import func
    
    # Get user's comics statistics
    stats = db.query(
        func.count(Comic.id).label('total_comics'),
        func.sum(Comic.total_views).label('total_views'),
        func.sum(Comic.total_likes).label('total_likes')
    ).filter(Comic.user_id == current_user.id_users).first()
    
    return {
        "ok": True,
        "data": {
            "rating": current_user.previous_rating,
            "rating_name": current_user.previous_rating_name,
            "total_comics": stats.total_comics or 0,
            "total_views": stats.total_views or 0,
            "total_likes": stats.total_likes or 0
        }
    }


@router.get("/profile/update-quota", response_model=dict)
async def get_update_quota(
    current_user: User = Depends(get_current_user)
):
    """
    Get remaining quota for profile updates
    
    Returns remaining quota for name/username changes
    """
    # TODO: Implement quota tracking from profile_updates_log table
    remaining_quota = 3  # Default quota
    
    return {
        "ok": True,
        "data": {
            "remaining_quota": remaining_quota,
            "quota_resets_at": None  # TODO: Calculate reset date
        }
    }


@router.get("/profile/debug-kredit", response_model=dict)
async def debug_kredit(
    current_user: User = Depends(get_current_user)
):
    """
    Debug endpoint to check current credits
    
    Returns current kredit balance
    """
    return {
        "ok": True,
        "data": {
            "user_id": current_user.id_users,
            "kredit": current_user.kredit,
            "balance": current_user.balance
        }
    }
