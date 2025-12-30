"""
User Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, validator, ConfigDict
from typing import Optional
from datetime import datetime
from app.schemas.common import ORMConfig


# ============ Request Schemas ============

class UserRegister(BaseModel):
    """Schema for user registration"""
    full_name: str = Field(..., min_length=2, max_length=100)
    phone_number: str = Field(..., min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=6)
    referral_code: Optional[str] = None  # Code of person who referred them
    
    @validator('phone_number')
    def validate_phone(cls, v):
        # Remove non-numeric characters
        cleaned = ''.join(filter(str.isdigit, v))
        if not cleaned:
            raise ValueError('Phone number must contain digits')
        return cleaned


class UserLogin(BaseModel):
    """Schema for user login"""
    identifier: Optional[str] = Field(None, description="Email or phone number")
    phone_number: Optional[str] = Field(None, description="Alternative to identifier")
    password: str = Field(..., min_length=6)


class UserVerify(BaseModel):
    """Schema for OTP verification"""
    phone_number: str
    verification_code: str = Field(..., min_length=6, max_length=6)


class ResendVerification(BaseModel):
    """Schema for resending verification code"""
    phone_number: str


class ChangePassword(BaseModel):
    """Schema for changing password"""
    old_password: str
    new_password: str = Field(..., min_length=6)


class SendResetToken(BaseModel):
    """Schema for sending password reset token"""
    phone_number: str


class VerifyResetToken(BaseModel):
    """Schema for verifying reset token"""
    phone_number: str
    reset_token: str


class ResetPassword(BaseModel):
    """Schema for resetting password"""
    phone_number: str
    reset_token: str
    new_password: str = Field(..., min_length=6)


class UpdateProfile(BaseModel):
    """Schema for updating profile details"""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None


class UpdateKredit(BaseModel):
    """Schema for updating user credits"""
    amount: int = Field(..., description="Amount to add/subtract") # Credits amount
    operation: str = Field(..., pattern="^(add|subtract)$", alias="type")
    description: Optional[str] = None
    
    model_config = ConfigDict(populate_by_name=True)


class UpdateFCMToken(BaseModel):
    """Schema for updating FCM token"""
    fcm_token: str


class GoogleTokenVerify(BaseModel):
    """Schema for Google OAuth token verification"""
    id_token: str


# ============ Response Schemas ============

class UserBase(BaseModel):
    """Base user schema"""
    id_users: int
    full_name: str
    username: Optional[str]
    email: Optional[str]
    phone_number: str
    
    model_config = ORMConfig


class UserResponse(UserBase):
    """Full user response schema"""
    referral_code_id: str
    is_verified: bool
    region: Optional[str]
    city: Optional[str]
    role: str
    login_method: str
    kredit: int
    balance: int
    profile_photo_path: Optional[str]
    publish_quota: int
    previous_rating: Optional[int]
    previous_rating_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    model_config = ORMConfig


class UserPublic(UserBase):
    """Public user info (for comments, etc.)"""
    profile_photo_path: Optional[str]
    previous_rating: Optional[int]
    previous_rating_name: Optional[str]
    
    model_config = ORMConfig


class ProfileRating(BaseModel):
    """User profile rating response"""
    rating: Optional[int]
    rating_name: Optional[str]
    total_comics: int
    total_views: int
    total_likes: int


class ReferralCodeResponse(BaseModel):
    """Referral code response"""
    referral_code: str
    total_referrals: int
    total_bonus_earned: int
