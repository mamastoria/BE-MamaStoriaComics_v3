"""
History API endpoints
User's comic read history
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.comic import Comic, ComicView
from app.schemas.comic import ComicListItem
from app.utils.pagination import paginate, get_pagination_params
from app.utils.responses import paginated_response

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/comics/last-read", response_model=dict)
async def get_read_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's comic read history
    
    - **page**: Page number
    - **per_page**: Items per page
    
    Returns paginated list of comics user has read, ordered by most recent
    """
    try:
        # Query comic views for current user
        query = db.query(Comic).join(
            ComicView,
            Comic.id == ComicView.comic_id
        ).options(
            joinedload(Comic.user)  # Eager load creator
        ).filter(
            ComicView.user_id == current_user.id_users
        ).order_by(ComicView.updated_at.desc())
        
        # Paginate
        page, per_page = get_pagination_params(page, per_page)
        items, total = paginate(query, page, per_page)
        
        # Convert to schema with error handling for individual items
        comics_data = []
        for comic in items:
            try:
                # Explicitly validate to catch model errors
                item_data = ComicListItem.model_validate(comic).model_dump()
                comics_data.append(item_data)
            except Exception as validation_error:
                logger.error(f"Failed to validate comic {comic.id}: {validation_error}")
                # Continue with other items or add a fallback? 
                # For now, we skip or add partial? Best to skip bad items to avoid breaking the whole list.
                continue
            
        return paginated_response(comics_data, page, per_page, total)
        
    except Exception as e:
        logger.error(f"Error fetching read history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(e)}"
        )
