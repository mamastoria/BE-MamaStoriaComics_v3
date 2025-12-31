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


from app.utils.pagination import paginate, get_pagination_params
from app.utils.responses import paginated_response

@router.get("/referrals", response_model=dict)
async def list_referrals_by_user(
    user_id: int = Query(..., description="User ID to get referrals for"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List referrals made by a specific user

    - **user_id**: User ID of the referrer
    - **page**: Page number
    - **per_page**: Items per page
    """
    # Check if user exists
    user = db.query(User).filter(User.id_users == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get referrals query
    query = db.query(Referral).options(
        joinedload(Referral.referred_user)
    ).filter(Referral.referrer_id == user_id)

    # Paginate
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)

    # Format response data
    referrals_data = []
    for referral in items:
        referral_dict = ReferralWithUser.model_validate(referral).model_dump()
        # Add referred user details
        referral_dict["referred_user"] = {
            "id_users": referral.referred_user.id_users,
            "username": referral.referred_user.username,
            "full_name": referral.referred_user.full_name,
            "phone_number": referral.referred_user.phone_number,
            "profile_photo_path": referral.referred_user.profile_photo_path,
            "created_at": referral.referred_user.created_at.isoformat() if referral.referred_user.created_at else None
        }
        referrals_data.append(referral_dict)

    return paginated_response(referrals_data, page, per_page, total)

@router.get("/referrals/check-parent", response_model=dict)
async def check_parent_referral(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if the current user has a parent referrer (was referred by someone)
    
    Returns details of the referrer if exists, otherwise null
    """
    if not current_user.referrals_for:
        return {
            "ok": True,
            "data": False
        }
        
    # Find the referrer user using the referral code
    referrer = db.query(User).filter(User.referral_code_id == current_user.referrals_for).first()
    
    if not referrer:
        return {
            "ok": True,
            "data": False
        }
        
    return {
        "ok": True,
        "data": True
    }