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

from pydantic import BaseModel, Field

class ReferralCreate(BaseModel):
    user_id: int = Field(..., description="User ID redeeming the code")
    referral_code: str = Field(..., description="Referral code to redeem")

@router.post("/referrals", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_referral(
    referral_data: ReferralCreate,
    db: Session = Depends(get_db)
):
    """
    Redeem a referral code (Set parent referrer)
    **Public Endpoint**: Does not require authentication header.
    
    - **user_id**: The ID of the user submitting the code
    - **referral_code**: The code of the referrer
    """
    code = referral_data.referral_code.strip()
    user_id = referral_data.user_id
    
    # 0. Get the user
    current_user = db.query(User).filter(User.id_users == user_id).first()
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 1. Check if user already has a referrer
    if current_user.referrals_for:
        # Check if it's the same code
        if current_user.referrals_for == code:
             return {"ok": True, "message": "Referral code already applied"}
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a referrer set"
        )
    
    # 2. Check if trying to refer self
    if current_user.referral_code_id == code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot use your own referral code"
        )

    # 3. Find the referrer
    referrer = db.query(User).filter(User.referral_code_id == code).first()
    if not referrer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid referral code"
        )
    
    try:
        # 4. Update User
        current_user.referrals_for = code
        
        # 5. Create Referral Record
        new_referral = Referral(
            referrer_id=referrer.id_users,
            referred_user_id=current_user.id_users
        )
        db.add(new_referral)
        
        db.commit()
        
        return {
            "ok": True, 
            "message": "Referral code verified successfully",
            "data": {
                "referrer_name": referrer.full_name,
                "referrer_code": code
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process referral: {str(e)}"
        )

@router.get("/referrals/check-parent", response_model=dict)
async def check_parent_referral(
    user_id: int = Query(..., description="User ID to check"),
    db: Session = Depends(get_db)
):
    """
    Check if the specific user has a parent referrer (was referred by someone)
    **Public Endpoint**: Does not require authentication header.
    
    Returns details of the referrer if exists, otherwise null
    """
    # 0. Get the user
    user = db.query(User).filter(User.id_users == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.referrals_for:
        return {
            "ok": True,
            "data": None
        }
        
    # Find the referrer user using the referral code
    referrer = db.query(User).filter(User.referral_code_id == user.referrals_for).first()
    
    if not referrer:
        return {
            "ok": True,
            "data": None
        }
        
    return {
        "ok": True,
        "data": {
            "id_users": referrer.id_users,
            "full_name": referrer.full_name,
            "username": referrer.username,
            "referral_code": referrer.referral_code_id,
            "profile_photo_path": referrer.profile_photo_path
        }
    }