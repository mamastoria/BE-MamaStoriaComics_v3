from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.follow import Follow
from app.schemas.user import UserPublic

router = APIRouter()

@router.post("/users/{user_id}/follow", response_model=dict)
async def follow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Follow a user
    """
    # Check if user to follow exists
    target_user = db.query(User).filter(User.id_users == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_id == current_user.id_users:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
        
    # Check if already following
    existing = db.query(Follow).filter(
        Follow.follower_id == current_user.id_users,
        Follow.following_id == user_id
    ).first()
    
    if existing:
        return {"ok": True, "message": "Already following"}
        
    # Create follow
    follow = Follow(follower_id=current_user.id_users, following_id=user_id)
    db.add(follow)
    db.commit()
    
    return {"ok": True, "message": "Followed successfully"}

@router.delete("/users/{user_id}/follow", response_model=dict)
async def unfollow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unfollow a user
    """
    follow = db.query(Follow).filter(
        Follow.follower_id == current_user.id_users,
        Follow.following_id == user_id
    ).first()
    
    if not follow:
        return {"ok": True, "message": "Not following"}
        
    db.delete(follow)
    db.commit()
    
    return {"ok": True, "message": "Unfollowed successfully"}

@router.get("/users/{user_id}/followers", response_model=dict)
async def get_followers(
    user_id: int,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Get users following the specified user
    """
    # Get followers
    followers_query = db.query(User).join(Follow, Follow.follower_id == User.id_users).filter(Follow.following_id == user_id)
    total = followers_query.count()
    followers = followers_query.offset(skip).limit(limit).all()
    
    return {
        "ok": True, 
        "data": [UserPublic.model_validate(u).model_dump() for u in followers],
        "total": total
    }

@router.get("/users/{user_id}/following", response_model=dict)
async def get_following(
    user_id: int,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Get users that the specified user follows
    """
    # Get following
    following_query = db.query(User).join(Follow, Follow.following_id == User.id_users).filter(Follow.follower_id == user_id)
    total = following_query.count()
    following = following_query.offset(skip).limit(limit).all()
    
    return {
        "ok": True, 
        "data": [UserPublic.model_validate(u).model_dump() for u in following],
        "total": total
    }

@router.get("/users/{user_id}/is-following", response_model=dict)
async def check_is_following(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if current user is following the target user
    """
    is_following = db.query(Follow).filter(
        Follow.follower_id == current_user.id_users,
        Follow.following_id == user_id
    ).first() is not None
    
    return {
        "ok": True,
        "data": {
            "is_following": is_following
        }
    }

@router.get("/users/{user_id}/follow-counts", response_model=dict)
async def get_follow_counts(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get follower and following counts only
    """
    followers_count = db.query(Follow).filter(Follow.following_id == user_id).count()
    following_count = db.query(Follow).filter(Follow.follower_id == user_id).count()
    
    return {
        "ok": True,
        "data": {
            "followers_count": followers_count,
            "following_count": following_count
        }
    }
