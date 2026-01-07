"""
Public API endpoints - No authentication required
These endpoints are accessible without login for public sharing
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
import logging
from typing import Optional

from app.core.database import get_db
from app.models.comic import Comic
from app.schemas.comic import ComicWithPanels, ComicListItem
from app.utils.pagination import paginate, get_pagination_params
from app.utils.responses import paginated_response

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/comics", response_model=dict)
async def list_public_comics(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    genre: Optional[str] = None,
    style: Optional[str] = None,
    q: Optional[str] = None,
    sort_by: Optional[str] = Query(None, regex="^(newest|popularity)$"),
    db: Session = Depends(get_db)
):
    """
    List all published comics with pagination - Public endpoint (no auth required)
    
    - **page**: Page number (default: 1)
    - **per_page**: Items per page (default: 20, max: 100)
    - **genre**: Filter by genre name
    - **style**: Filter by style name
    - **q**: Search query in title, synopsis, and tags
    - **sort_by**: Sort order - 'newest' (default) or 'popularity' (by total_likes + total_views)
    
    Returns comics ordered by newest first (created_at DESC) or popularity
    """
    # Base query - only published comics
    query = db.query(Comic).filter(
        Comic.title.isnot(None),
        Comic.cover_url.isnot(None),
        Comic.publisher.isnot(None)  # Only officially published comics
    )
    
    # Apply filters
    if genre:
        query = query.filter(Comic.genre.contains([genre]))
    
    if style:
        query = query.filter(Comic.style == style)
    
    if q:
        search_term = f"%{q}%"
        query = query.filter(
            (Comic.title.ilike(search_term)) | 
            (Comic.synopsis.ilike(search_term)) |
            (Comic.tags.ilike(search_term))
        )
    
    # Apply sorting
    if sort_by == "popularity":
        # Sort by popularity (total_likes + total_views)
        query = query.order_by(
            (Comic.total_likes + Comic.total_views).desc()
        )
    else:
        # Default: sort by newest (created_at)
        query = query.order_by(Comic.created_at.desc())
    
    # Paginate
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)
    
    # Convert to schema
    comics_data = [ComicListItem.model_validate(comic).model_dump() for comic in items]
    
    return paginated_response(comics_data, page, per_page, total)


@router.get("/comics/{comic_id}", response_model=dict)
async def get_public_comic_detail(
    comic_id: int,
    db: Session = Depends(get_db)
):
    """
    Get comic detail by ID - Public endpoint (no auth required)
    
    - **comic_id**: Comic ID
    
    Returns complete comic information including panels for public sharing
    """
    comic = db.query(Comic).options(
        joinedload(Comic.user),
        joinedload(Comic.panels)
    ).filter(Comic.id == comic_id).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Only show published comics (comics with title, cover, and publisher)
    if not comic.title or not comic.cover_url or not comic.publisher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Track view (without user since this is public)
    from app.services.comic_service import ComicService
    ComicService.track_comic_read(db, comic, user=None)
    
    return {
        "ok": True,
        "data": ComicWithPanels.model_validate(comic).model_dump()
    }


@router.get("/comics/{comic_id}/similar", response_model=dict)
async def get_public_similar_comics(
    comic_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get similar comics based on genre and style - Public endpoint (no auth required)
    
    - **comic_id**: Comic ID
    - **limit**: Number of similar comics (max: 50)
    
    Returns similar comics ordered by newest first (created_at DESC)
    """
    comic = db.query(Comic).filter(Comic.id == comic_id).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Get similar comics using service
    from app.services.comic_service import ComicService
    similar = ComicService.get_similar_comics(db, comic, limit)
    similar_data = [ComicListItem.model_validate(c).model_dump() for c in similar]
    
    return {
        "ok": True,
        "data": similar_data
    }
