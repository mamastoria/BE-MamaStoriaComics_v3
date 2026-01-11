"""
Withdrawal API endpoints
List and add withdrawals
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from sqlalchemy.sql import func

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.withdrawal import Withdrawal
from app.schemas.withdrawal import WithdrawalCreate, WithdrawalResponse

router = APIRouter()


from app.utils.pagination import paginate, get_pagination_params
from app.utils.responses import paginated_response
from fastapi import Query

@router.get("/withdrawals", response_model=dict)
async def list_withdrawals(
    id_user: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List withdrawals for a specific user

    - **id_user**: User ID (required)
    - **page**: Page number
    - **per_page**: Items per page
    - **start_date**: Filter by start date (YYYY-MM-DD)
    - **end_date**: Filter by end date (YYYY-MM-DD)
    """
    query = db.query(Withdrawal).filter(Withdrawal.id_user == id_user)

    if start_date:
        query = query.filter(func.date(Withdrawal.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(Withdrawal.created_at) <= end_date)

    # Calculate total withdrawal for the user (before pagination)
    from sqlalchemy import func
    total_withdrawal = db.query(func.sum(Withdrawal.amount)).filter(Withdrawal.id_user == id_user).scalar() or 0

    # Paginate
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)

    data = [WithdrawalResponse.model_validate(withdrawal).model_dump() for withdrawal in items]

    response = paginated_response(data, page, per_page, total)
    response["total_withdrawal"] = total_withdrawal
    return response


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
    - **status**: Withdrawal status (optional, defaults to pending)
    - **bank_name**: (Optional)
    - **account_number**: (Optional)
    - **account_name**: (Optional)
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
        status=withdrawal_data.status or "pending", # Ensure status is not None
        bank_name=withdrawal_data.bank_name,
        account_number=withdrawal_data.account_number,
        account_name=withdrawal_data.account_name
    )

    db.add(new_withdrawal)
    db.commit()
    db.refresh(new_withdrawal)

    # Send Notification Email to Admin
    try:
        from app.utils.email import send_email
        from app.core.config import settings
        from app.models.config_app import Config
        
        # Get recipient email from database config
        email_config = db.query(Config).filter(Config.name_config == 'email_withdrawal').first()
        to_email = email_config.value_config if email_config else settings.SMTP_USERNAME
        
        # Only send if we have a valid email
        if to_email:
            subject = f"[Withdrawal Request] ID:{new_withdrawal.id} - {user.username} - Rp {new_withdrawal.amount:,}"
            
            html_content = f"""
            <h2>New Withdrawal Request</h2>
            <table style="border-collapse: collapse; width: 100%;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>User:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{user.full_name} ({user.email})</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Amount:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">Rp {new_withdrawal.amount:,}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Bank:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{new_withdrawal.bank_name}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Account Number:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{new_withdrawal.account_number}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Account Name:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{new_withdrawal.account_name}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Date:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{new_withdrawal.created_at}</td></tr>
            </table>
            <p>Please review and process in Admin Dashboard.</p>
            """
            
            send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content
            )
            print(f"Withdrawal email sent to {to_email}")
        else:
            print("No email configuration found for 'email_withdrawal' and no SMTP_USERNAME set.")

    except Exception as e:
        print(f"Failed to send withdrawal email: {e}")

    return {
        "ok": True,
        "message": "Withdrawal added successfully",
        "data": WithdrawalResponse.model_validate(new_withdrawal).model_dump()
    }