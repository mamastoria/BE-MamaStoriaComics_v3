"""
Referral API endpoints
List referrals by user
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.referral import Referral
from app.schemas.referral import ReferralWithUser

router = APIRouter()


@router.get("/referrals", response_model=dict)
async def list_referrals_by_user(
    user_id: int = Query(..., description="User ID to get referrals for"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List referrals made by a specific user

    - **user_id**: User ID of the referrer
    """
    # Check if user exists
    user = db.query(User).filter(User.id_users == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get referrals with referred user details
    referrals = db.query(Referral).options(
        joinedload(Referral.referred_user)
    ).filter(Referral.referrer_id == user_id).all()

    # Format response data
    referrals_data = []
    for referral in referrals:
        referral_dict = ReferralWithUser.model_validate(referral).model_dump()
        # Add referred user details
        referral_dict["referred_user"] = {
            "id_users": referral.referred_user.id_users,
            "username": referral.referred_user.username,
            "full_name": referral.referred_user.full_name,
            "email": referral.referred_user.email,
            "profile_photo_path": referral.referred_user.profile_photo_path,
            "created_at": referral.referred_user.created_at.isoformat() if referral.referred_user.created_at else None
        }
        referrals_data.append(referral_dict)

    return {
        "ok": True,
        "data": referrals_data,
        "total": len(referrals_data)
    }