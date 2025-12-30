"""
Commission API endpoints
List and add commissions
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.commission import Commission
from app.schemas.commission import CommissionCreate, CommissionResponse

router = APIRouter()


@router.get("/commissions", response_model=dict)
async def list_commissions(
    id_user: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List commissions for a specific user

    - **id_user**: User ID (required)
    """
    commissions = db.query(Commission).filter(Commission.id_user == id_user).all()

    # Calculate total commission for the user
    from sqlalchemy import func
    total_commission = db.query(func.sum(Commission.kredit)).filter(Commission.id_user == id_user).scalar() or 0

    return {
        "ok": True,
        "data": [CommissionResponse.model_validate(commission).model_dump() for commission in commissions],
        "total_commission": total_commission
    }


@router.post("/commissions", response_model=dict)
async def add_commission(
    commission_data: CommissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a new commission

    - **id_user**: User ID
    - **kredit**: Commission credit amount
    - **keterangan**: Commission description
    """
    # Check if user exists
    user = db.query(User).filter(User.id_users == commission_data.id_user).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Create commission
    new_commission = Commission(
        id_user=commission_data.id_user,
        kredit=commission_data.kredit,
        keterangan=commission_data.keterangan
    )

    db.add(new_commission)
    db.commit()
    db.refresh(new_commission)

    return {
        "ok": True,
        "message": "Commission added successfully",
        "data": CommissionResponse.model_validate(new_commission).model_dump()
    }