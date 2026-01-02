"""
Comments API endpoints
Comic comments and reviews
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
import logging
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.comic import Comic
from app.models.comment import Comment
from app.schemas.user import UserPublic
from app.utils.pagination import paginate, get_pagination_params
from app.utils.responses import paginated_response
from pydantic import BaseModel, Field
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)


# Schemas
class CommentCreate(BaseModel):
    """Schema for creating comment"""
    content: str = Field(..., min_length=1, max_length=1000)
    rating: Optional[int] = Field(None, ge=1, le=5)


class CommentResponse(BaseModel):
    """Schema for comment response"""
    id: int
    comic_id: int
    user_id: int
    content: str
    rating: Optional[int]
    created_at: datetime
    updated_at: datetime
    user: Optional[UserPublic] = None
    
    class Config:
        from_attributes = True


@router.get("/comics/{comic}/review_comments", response_model=dict)
@router.get("/comics/{comic}/comments", response_model=dict)
async def list_comments(
    comic: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all comments for a comic
    
    - **comic**: Comic ID
    - **page**: Page number
    - **per_page**: Items per page
    
    Returns paginated list of comments with user info
    """
    # Check if comic exists
    comic_obj = db.query(Comic).filter(Comic.id == comic).first()
    if not comic_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Query comments
    query = db.query(Comment).options(
        joinedload(Comment.user)
    ).filter(
        Comment.comic_id == comic
    ).order_by(Comment.created_at.desc())
    
    # Paginate
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)
    
    # Convert to schema with user info
    comments_data = []
    for comment in items:
        try:
            comment_dict = CommentResponse.model_validate(comment).model_dump()
            # Add user info if available (joinedload handles this safely)
            if comment.user:
                comment_dict['user'] = UserPublic.model_validate(comment.user).model_dump()
            comments_data.append(comment_dict)
        except Exception as e:
            logger.error(f"Error processing comment {comment.id}: {e}")
            continue
    
    return paginated_response(comments_data, page, per_page, total)


@router.post("/comics/{comic}/comments", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_comment(
    comic: int,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add comment/review to a comic
    
    - **comic**: Comic ID
    - **content**: Comment text (1-1000 characters)
    - **rating**: Optional rating (1-5 stars)
    
    Returns created comment
    """
    # Check if comic exists
    comic_obj = db.query(Comic).filter(Comic.id == comic).first()
    if not comic_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Create comment
    comment = Comment(
        comic_id=comic,
        user_id=current_user.id_users,
        content=comment_data.content,
        rating=comment_data.rating
    )
    
    db.add(comment)
    
    # Update comic comment count
    comic_obj.total_comments += 1
    
    db.commit()
    db.refresh(comment)

    # Notify author and check milestones
    try:
        from app.models.notification import Notification
        from app.services.push_notification_service import send_push_notification

        # 1. Notify Author (if not self-comment)
        if comic_obj.user_id != current_user.id_users:
            author = comic_obj.user
            
            # Create snippet for message
            snippet = comment_data.content[:50] + "..." if len(comment_data.content) > 50 else comment_data.content

            # DB Notification
            notif = Notification(
                user_id=comic_obj.user_id,
                type="new_comment",
                title="Komentar baru di komikmu! 💬",
                message=f"{current_user.full_name or current_user.username} mengomentari: {snippet}",
                data=f'{{"comic_id": {comic}, "comment_id": {comment.id}}}'
            )
            db.add(notif)
            
            # Push Notification
            if author and author.fcm_token:
                send_push_notification(
                    fcm_token=author.fcm_token,
                    title="Komentar baru di komikmu! 💬",
                    body=f"{current_user.full_name or current_user.username} mengomentari: {snippet}",
                    data={"comic_id": str(comic), "comment_id": str(comment.id), "type": "new_comment"}
                )

        # 2. Check Milestones (Comments)
        milestones = [10, 50, 100, 500, 1000]
        if comic_obj.total_comments in milestones:
            # DB Notification
            notif_milestone = Notification(
                user_id=comic_obj.user_id,
                type="milestone",
                title="Komikmu Ramai Dibicarakan! 🗣️",
                message=f"Selamat! Komik '{comic_obj.title or 'Unknown'}' sudah mencapai {comic_obj.total_comments} komentar!",
                data=f'{{"comic_id": {comic}, "total_comments": {comic_obj.total_comments}}}'
            )
            db.add(notif_milestone)
            
            # Push Notification
            if comic_obj.user and comic_obj.user.fcm_token:
                 send_push_notification(
                    fcm_token=comic_obj.user.fcm_token,
                    title="Komikmu Ramai Dibicarakan! 🗣️",
                    body=f"Selamat! Komik '{comic_obj.title or 'Unknown'}' sudah mencapai {comic_obj.total_comments} komentar!",
                    data={"comic_id": str(comic), "type": "milestone"}
                )

        db.commit()
    except Exception as e:
        logger.error(f"Failed to send comment notification: {e}")

    
    # Prepare response with user info
    comment_dict = CommentResponse.model_validate(comment).model_dump()
    comment_dict['user'] = UserPublic.model_validate(current_user).model_dump()
    
    return {
        "ok": True,
        "message": "Comment added successfully",
        "data": comment_dict
    }


@router.delete("/comments/{comment_id}", response_model=dict)
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a comment (only comment owner can delete)
    
    - **comment_id**: Comment ID
    """
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    # Check ownership
    if comment.user_id != current_user.id_users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments"
        )
    
    # Update comic comment count
    comic = db.query(Comic).filter(Comic.id == comment.comic_id).first()
    if comic:
        comic.total_comments = max(0, comic.total_comments - 1)
    
    db.delete(comment)
    db.commit()
    
    return {
        "ok": True,
        "message": "Comment deleted successfully"
    }
