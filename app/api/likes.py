"""
Likes API endpoints
Comic likes/favorites
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.comic import Comic, ComicUser
from app.schemas.user import UserPublic
from app.utils.pagination import paginate, get_pagination_params
from app.utils.responses import paginated_response
from pydantic import BaseModel

router = APIRouter()


# Schemas
class LikeResponse(BaseModel):
    """Schema for like response"""
    user_id: int
    comic_id: int
    created_at: datetime
    user: Optional[UserPublic] = None
    
    class Config:
        from_attributes = True


class LikeStatusResponse(BaseModel):
    """Schema for like status"""
    is_liked: bool
    total_likes: int


@router.get("/comics/{comic}/likes", response_model=dict)
async def list_likes(
    comic: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all users who liked a comic
    
    - **comic**: Comic ID
    - **page**: Page number
    - **per_page**: Items per page
    
    Returns paginated list of users who liked the comic
    """
    # Check if comic exists
    comic_obj = db.query(Comic).filter(Comic.id == comic).first()
    if not comic_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Query likes
    # Query likes with User join for performance
    query = db.query(ComicUser, User).join(
        User, ComicUser.user_id == User.id_users
    ).filter(
        ComicUser.comic_id == comic
    ).order_by(ComicUser.created_at.desc())
    
    # Paginate
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)
    
    # Get user info for each like
    likes_data = []
    for like, user in items:
        try:
            if user:
                likes_data.append({
                    "user_id": like.user_id,
                    "comic_id": like.comic_id,
                    "created_at": like.created_at,
                    "user": UserPublic.model_validate(user).model_dump()
                })
        except Exception:
            continue
    
    return paginated_response(likes_data, page, per_page, total)


@router.post("/comics/{comic}/likes", response_model=dict, status_code=status.HTTP_201_CREATED)
async def like_comic(
    comic: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Like a comic
    
    - **comic**: Comic ID
    
    Adds comic to user's favorites
    """
    # Check if comic exists
    comic_obj = db.query(Comic).filter(Comic.id == comic).first()
    if not comic_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Check if already liked
    existing = db.query(ComicUser).filter(
        ComicUser.comic_id == comic,
        ComicUser.user_id == current_user.id_users
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comic already liked"
        )
    
    # Create like
    like = ComicUser(
        comic_id=comic,
        user_id=current_user.id_users
    )
    
    db.add(like)
    
    # Update comic like count
    comic_obj.total_likes += 1
    
    db.commit()
    
    return {
        "ok": True,
        "message": "Comic liked successfully",
        "data": {
            "total_likes": comic_obj.total_likes
        }
    }


@router.delete("/comics/{comic}/likes", response_model=dict)
async def unlike_comic(
    comic: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unlike a comic
    
    - **comic**: Comic ID
    
    Removes comic from user's favorites
    """
    # Check if comic exists
    comic_obj = db.query(Comic).filter(Comic.id == comic).first()
    if not comic_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Find like
    like = db.query(ComicUser).filter(
        ComicUser.comic_id == comic,
        ComicUser.user_id == current_user.id_users
    ).first()
    
    if not like:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comic not liked yet"
        )
    
    # Delete like
    db.delete(like)
    
    # Update comic like count
    comic_obj.total_likes = max(0, comic_obj.total_likes - 1)
    
    db.commit()
    
    return {
        "ok": True,
        "message": "Comic unliked successfully",
        "data": {
            "total_likes": comic_obj.total_likes
        }
    }


@router.get("/comics/{comic}/likes/status", response_model=dict)
async def get_like_status(
    comic: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if current user has liked a comic
    
    - **comic**: Comic ID
    
    Returns like status and total likes count
    """
    # Check if comic exists
    comic_obj = db.query(Comic).filter(Comic.id == comic).first()
    if not comic_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Check if user liked
    is_liked = db.query(ComicUser).filter(
        ComicUser.comic_id == comic,
        ComicUser.user_id == current_user.id_users
    ).first() is not None
    
    return {
        "ok": True,
        "data": {
            "is_liked": is_liked,
            "total_likes": comic_obj.total_likes
        }
    }
