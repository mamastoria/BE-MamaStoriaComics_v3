"""
Analytics API endpoints
User statistics and analytics
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.comic import Comic
from app.models.subscription import Transaction

router = APIRouter()


# Schemas
class DashboardStats(BaseModel):
    """Dashboard statistics"""
    total_comics: int
    total_views: int
    total_likes: int
    total_comments: int
    total_earnings: int
    active_subscription: bool
    publish_quota: int


class DailyStats(BaseModel):
    """Daily statistics"""
    date: str
    views: int
    likes: int
    comments: int


class MonthlyStats(BaseModel):
    """Monthly statistics"""
    month: str
    views: int
    likes: int
    comments: int
    earnings: int


class TransactionHistory(BaseModel):
    """Transaction history item"""
    id: int
    type: str
    amount: int
    description: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/analytics/dashboard", response_model=dict)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get dashboard statistics
    
    Returns overview statistics for user's dashboard including:
    - Total comics created
    - Total views, likes, comments
    - Total earnings
    - Subscription status
    - Publish quota
    """
    # Get comics statistics
    comics_stats = db.query(
        func.count(Comic.id).label('total_comics'),
        func.coalesce(func.sum(Comic.total_views), 0).label('total_views'),
        func.coalesce(func.sum(Comic.total_likes), 0).label('total_likes'),
        func.coalesce(func.sum(Comic.total_comments), 0).label('total_comments')
    ).filter(
        Comic.user_id == current_user.id_users
    ).first()
    
    # Get total earnings from transactions
    earnings = db.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id_users,
        Transaction.type == 'credit'
    ).scalar() or 0
    
    # Check active subscription
    from app.models.subscription import Subscription
    has_subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id_users,
        Subscription.status == 'active',
        Subscription.end_date > datetime.utcnow()
    ).first() is not None
    
    return {
        "ok": True,
        "data": {
            "total_comics": comics_stats.total_comics or 0,
            "total_views": int(comics_stats.total_views or 0),
            "total_likes": int(comics_stats.total_likes or 0),
            "total_comments": int(comics_stats.total_comments or 0),
            "total_earnings": int(earnings),
            "active_subscription": has_subscription,
            "publish_quota": current_user.publish_quota,
            "current_balance": current_user.balance,
            "current_credits": current_user.kredit
        }
    }


@router.get("/analytics/daily", response_model=dict)
async def get_daily_stats(
    days: int = Query(7, ge=1, le=90, description="Number of days to retrieve"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get daily statistics
    
    - **days**: Number of days to retrieve (1-90, default: 7)
    
    Returns daily statistics for the specified number of days
    """
    # Calculate date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days - 1)
    
    # Get daily stats (simplified - in production, you'd have a views_log table)
    # For now, we'll return mock data structure
    daily_stats = []
    
    for i in range(days):
        date = start_date + timedelta(days=i)
        
        # Get comics created on this date
        comics_on_date = db.query(Comic).filter(
            Comic.user_id == current_user.id_users,
            func.date(Comic.created_at) == date
        ).all()
        
        # Sum up stats (this is simplified - ideally you'd track daily changes)
        total_views = sum(comic.total_views for comic in comics_on_date)
        total_likes = sum(comic.total_likes for comic in comics_on_date)
        total_comments = sum(comic.total_comments for comic in comics_on_date)
        
        daily_stats.append({
            "date": date.isoformat(),
            "views": total_views,
            "likes": total_likes,
            "comments": total_comments
        })
    
    return {
        "ok": True,
        "data": daily_stats
    }


@router.get("/analytics/monthly", response_model=dict)
async def get_monthly_stats(
    months: int = Query(6, ge=1, le=24, description="Number of months to retrieve"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get monthly statistics
    
    - **months**: Number of months to retrieve (1-24, default: 6)
    
    Returns monthly statistics for the specified number of months
    """
    monthly_stats = []
    
    for i in range(months):
        # Calculate month
        target_date = datetime.utcnow() - timedelta(days=30 * i)
        month_str = target_date.strftime("%Y-%m")
        
        # Get comics created in this month
        comics_in_month = db.query(Comic).filter(
            Comic.user_id == current_user.id_users,
            extract('year', Comic.created_at) == target_date.year,
            extract('month', Comic.created_at) == target_date.month
        ).all()
        
        # Get earnings in this month
        earnings = db.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.user_id == current_user.id_users,
            Transaction.type == 'credit',
            extract('year', Transaction.created_at) == target_date.year,
            extract('month', Transaction.created_at) == target_date.month
        ).scalar() or 0
        
        # Sum up stats
        total_views = sum(comic.total_views for comic in comics_in_month)
        total_likes = sum(comic.total_likes for comic in comics_in_month)
        total_comments = sum(comic.total_comments for comic in comics_in_month)
        
        monthly_stats.append({
            "month": month_str,
            "views": total_views,
            "likes": total_likes,
            "comments": total_comments,
            "earnings": int(earnings)
        })
    
    # Reverse to show oldest first
    monthly_stats.reverse()
    
    return {
        "ok": True,
        "data": monthly_stats
    }


@router.get("/analytics/yearly", response_model=dict)
async def get_yearly_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get yearly statistics
    
    Returns statistics for the current year
    """
    current_year = datetime.utcnow().year
    
    # Get all comics for current year
    comics_this_year = db.query(Comic).filter(
        Comic.user_id == current_user.id_users,
        extract('year', Comic.created_at) == current_year
    ).all()
    
    # Get earnings for current year
    earnings = db.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id_users,
        Transaction.type == 'credit',
        extract('year', Transaction.created_at) == current_year
    ).scalar() or 0
    
    # Calculate totals
    total_comics = len(comics_this_year)
    total_views = sum(comic.total_views for comic in comics_this_year)
    total_likes = sum(comic.total_likes for comic in comics_this_year)
    total_comments = sum(comic.total_comments for comic in comics_this_year)
    
    return {
        "ok": True,
        "data": {
            "year": current_year,
            "total_comics": total_comics,
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_earnings": int(earnings)
        }
    }


@router.get("/analytics/history", response_model=dict)
async def get_transaction_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get transaction history
    
    - **page**: Page number
    - **per_page**: Items per page
    
    Returns paginated transaction history ordered by most recent
    """
    from app.utils.pagination import paginate, get_pagination_params
    from app.utils.responses import paginated_response
    
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id_users
    ).order_by(Transaction.created_at.desc())
    
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)
    
    transactions_data = [
        TransactionHistory.model_validate(txn).model_dump()
        for txn in items
    ]
    
    return paginated_response(transactions_data, page, per_page, total)
