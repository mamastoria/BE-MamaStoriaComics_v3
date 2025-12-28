"""
Comments API endpoints
Comic comments and reviews
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
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
    query = db.query(Comment).filter(
        Comment.comic_id == comic
    ).order_by(Comment.created_at.desc())
    
    # Paginate
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)
    
    # Convert to schema with user info
    comments_data = []
    for comment in items:
        comment_dict = CommentResponse.model_validate(comment).model_dump()
        # Add user info
        if comment.user:
            comment_dict['user'] = UserPublic.model_validate(comment.user).model_dump()
        comments_data.append(comment_dict)
    
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
