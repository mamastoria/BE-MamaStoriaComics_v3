"""
Referral Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field
from datetime import datetime
from app.schemas.common import ORMConfig


class ReferralBase(BaseModel):
    """Base referral schema"""
    referrer_id: int
    referred_user_id: int
    referral_code: str
    created_at: datetime
    updated_at: datetime

    model_config = ORMConfig


class ReferralResponse(ReferralBase):
    """Full referral response schema"""
    id: int
    pass


class ReferralWithUser(ReferralBase):
    """Referral response with referred user details"""
    id: int
    referred_user: dict  # User details
    pass