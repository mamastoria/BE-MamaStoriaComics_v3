"""
Notifications API endpoints
User notifications management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.utils.pagination import paginate, get_pagination_params
from app.utils.responses import paginated_response
from pydantic import BaseModel

router = APIRouter()


# Schemas
class NotificationCreate(BaseModel):
    """Schema for creating a notification"""
    user_id: int
    type: str
    title: str
    message: str
    data: Optional[str] = None


class NotificationResponse(BaseModel):
    """Notification response"""
    id: int
    type: str
    title: str
    message: str
    data: Optional[str]
    read_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/notifications", response_model=dict)
async def create_notification(
    notification_data: NotificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new notification

    - **user_id**: User ID to send notification to
    - **type**: Notification type (comment, like, milestone, etc.)
    - **title**: Notification title
    - **message**: Notification message
    - **data**: Optional JSON data
    """
    # Check if target user exists
    user = db.query(User).filter(User.id_users == notification_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Create notification
    new_notification = Notification(
        user_id=notification_data.user_id,
        type=notification_data.type,
        title=notification_data.title,
        message=notification_data.message,
        data=notification_data.data
    )

    db.add(new_notification)
    db.commit()
    db.refresh(new_notification)

    return {
        "ok": True,
        "message": "Notification created successfully",
        "data": NotificationResponse.model_validate(new_notification).model_dump()
    }


@router.get("/notifications", response_model=dict)
async def list_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's notifications
    
    - **page**: Page number
    - **per_page**: Items per page
    - **unread_only**: Filter to show only unread notifications
    
    Returns paginated list of notifications ordered by most recent
    """
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id_users
    )
    
    # Filter unread only
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    
    # Order by most recent
    query = query.order_by(Notification.created_at.desc())
    
    # Paginate
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)
    
    # Convert to schema
    notifications_data = [
        NotificationResponse.model_validate(notif).model_dump()
        for notif in items
    ]
    
    return paginated_response(notifications_data, page, per_page, total)


@router.get("/notifications/unread-count", response_model=dict)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get count of unread notifications
    
    Returns total number of unread notifications for current user
    """
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id_users,
        Notification.read_at.is_(None)
    ).count()
    
    return {
        "ok": True,
        "data": {
            "unread_count": count
        }
    }


@router.post("/notifications/mark-as-read", response_model=dict)
async def mark_notifications_as_read(
    notification_ids: list[int] = Query(..., description="List of notification IDs to mark as read"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark notifications as read
    
    - **notification_ids**: List of notification IDs to mark as read
    
    Marks specified notifications as read by setting read_at timestamp
    """
    # Get notifications
    notifications = db.query(Notification).filter(
        Notification.id.in_(notification_ids),
        Notification.user_id == current_user.id_users,
        Notification.read_at.is_(None)  # Only unread notifications
    ).all()
    
    if not notifications:
        return {
            "ok": True,
            "message": "No unread notifications found to mark as read"
        }
    
    # Mark as read
    now = datetime.utcnow()
    for notification in notifications:
        notification.read_at = now
    
    db.commit()
    
    return {
        "ok": True,
        "message": f"{len(notifications)} notification(s) marked as read"
    }


@router.post("/notifications/{notification_id}/mark-as-read", response_model=dict)
async def mark_single_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark single notification as read
    
    - **notification_id**: Notification ID
    """
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id_users
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    if notification.read_at:
        return {
            "ok": True,
            "message": "Notification already marked as read"
        }
    
    notification.read_at = datetime.utcnow()
    db.commit()
    
    return {
        "ok": True,
        "message": "Notification marked as read"
    }


@router.delete("/notifications/{notification_id}", response_model=dict)
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete notification
    
    - **notification_id**: Notification ID
    
    Permanently deletes the notification
    """
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id_users
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    db.delete(notification)
    db.commit()
    
    return {
        "ok": True,
        "message": "Notification deleted successfully"
    }


@router.post("/notifications/mark-all-as-read", response_model=dict)
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark all notifications as read
    
    Marks all unread notifications for current user as read
    """
    notifications = db.query(Notification).filter(
        Notification.user_id == current_user.id_users,
        Notification.read_at.is_(None)
    ).all()
    
    if not notifications:
        return {
            "ok": True,
            "message": "No unread notifications"
        }
    
    now = datetime.utcnow()
    for notification in notifications:
        notification.read_at = now
    
    db.commit()
    
    return {
        "ok": True,
        "message": f"All {len(notifications)} notification(s) marked as read"
    }

# Email Configuration
RESEND_KEY = "re_hsvmU2Zv_EjdhcaWUC7aRuUgfjfinhfVq"
RESEND_URL = "https://api.resend.com/emails"
RESEND_EMAIL_FROM = "onboarding@resend.dev"
RESEND_EMAIL_TO = "yapri177@gmail.com"


class SendEmailRequest(BaseModel):
    """Schema for sending email"""
    title: str
    message: str
    emailTo: str


@router.post("/notifications/send-email", response_model=dict)
async def send_email_notification(
    email_data: SendEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)  # Kept for consistency if needed later
):
    """
    Send email notification via Resend

    - **title**: Email subject
    - **message**: Email HTML body
    - **emailTo**: Recipient email address
    """
    import requests
    
    headers = {
        "Authorization": f"Bearer {RESEND_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "from": RESEND_EMAIL_FROM,
        "to": [email_data.emailTo],
        "subject": email_data.title,
        "html": f"<p>{email_data.message}</p>"
    }
    
    try:
        response = requests.post(RESEND_URL, json=payload, headers=headers)
        response.raise_for_status()
        
        return {
            "ok": True,
            "message": "Email sent successfully",
            "data": response.json()
        }
    except requests.exceptions.RequestException as e:
        error_detail = str(e)
        if response is not None:
             try:
                 error_detail = response.json()
             except:
                 error_detail = response.text
                 
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {error_detail}"
        )
