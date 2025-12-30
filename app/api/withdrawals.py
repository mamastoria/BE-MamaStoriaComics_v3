"""
Withdrawal API endpoints
List and add withdrawals
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.withdrawal import Withdrawal
from app.schemas.withdrawal import WithdrawalCreate, WithdrawalResponse

router = APIRouter()


@router.get("/withdrawals", response_model=dict)
async def list_withdrawals(
    id_user: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List withdrawals for a specific user

    - **id_user**: User ID (required)
    """
    withdrawals = db.query(Withdrawal).filter(Withdrawal.id_user == id_user).all()

    # Calculate total withdrawal for the user
    from sqlalchemy import func
    total_withdrawal = db.query(func.sum(Withdrawal.amount)).filter(Withdrawal.id_user == id_user).scalar() or 0

    return {
        "ok": True,
        "data": [WithdrawalResponse.model_validate(withdrawal).model_dump() for withdrawal in withdrawals],
        "total_withdrawal": total_withdrawal
    }


@router.post("/withdrawals", response_model=dict)
async def add_withdrawal(
    withdrawal_data: WithdrawalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a new withdrawal

    - **id_user**: User ID
    - **amount**: Withdrawal amount (must be > 0)
    - **status**: Withdrawal status
    """
    # Check if user exists
    user = db.query(User).filter(User.id_users == withdrawal_data.id_user).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Create withdrawal
    new_withdrawal = Withdrawal(
        id_user=withdrawal_data.id_user,
        amount=withdrawal_data.amount,
        status=withdrawal_data.status
    )

    db.add(new_withdrawal)
    db.commit()
    db.refresh(new_withdrawal)

    return {
        "ok": True,
        "message": "Withdrawal added successfully",
        "data": WithdrawalResponse.model_validate(new_withdrawal).model_dump()
    }