"""
Public API endpoints - No authentication required
These endpoints are accessible without login for public sharing
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import desc, func, String
from sqlalchemy.orm import Session, joinedload
import logging
from typing import Optional, List

from app.core.database import get_db
from app.models.comic import Comic
from app.models.user import User
from app.schemas.comic import ComicWithPanels, ComicListItem
from app.utils.pagination import paginate, get_pagination_params
from app.utils.responses import paginated_response
# Service import moved to inside functions to avoid circular imports if any, keeping consistency

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/comics/similar", response_model=dict)
async def get_similar_comics_via_query(
    comic_id: int = Query(..., description="ID komik referensi"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get similar comics based on genre and style - Public endpoint
    
    - **comic_id**: Comic ID (Query Param)
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
        Comic.cover_url.isnot(None)
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


@router.get("/comics/popular", response_model=dict)
async def list_popular_comics(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    nuance: Optional[str] = Query(None, description="Filter by genre/nuance"),
    db: Session = Depends(get_db)
):
    """
    List popular comics based on total_likes.
    """
    query = db.query(Comic).filter(
        Comic.title.isnot(None),
        Comic.cover_url.isnot(None)
    )
    
    if nuance:
        # Fallback to text searching if structure varies
        query = query.filter(func.cast(Comic.genre, String).ilike(f"%{nuance}%"))

    # Sort by total_likes DESC (Most Liked)
    query = query.order_by(Comic.total_likes.desc())
    
    items, total = paginate(query, page, limit)
    comics_data = [ComicListItem.model_validate(c).model_dump() for c in items]
    
    return paginated_response(comics_data, page, limit, total)


@router.get("/comics/trending", response_model=dict)
async def list_trending_comics(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List trending comics based on total_views.
    """
    query = db.query(Comic).filter(
        Comic.title.isnot(None),
        Comic.cover_url.isnot(None)
    )

    # Sort by total_views DESC (Most Viewed/Viral)
    query = query.order_by(Comic.total_views.desc())

    items, total = paginate(query, page, limit)
    comics_data = [ComicListItem.model_validate(c).model_dump() for c in items]
    
    return paginated_response(comics_data, page, limit, total)


@router.get("/comics/new", response_model=dict)
async def list_new_comics(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List newly released comics (created_at DESC).
    """
    query = db.query(Comic).filter(
        Comic.title.isnot(None),
        Comic.cover_url.isnot(None)
    ).order_by(desc(Comic.created_at))

    items, total = paginate(query, page, limit)
    comics_data = [ComicListItem.model_validate(c).model_dump() for c in items]
    
    return paginated_response(comics_data, page, limit, total)


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
    
    # Only show published comics (comics with title and cover)
    if not comic.title or not comic.cover_url:
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





@router.get("/creators", response_model=dict)
async def list_top_creators(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List creators sorted by number of published comics.
    """
    # Subquery or Join to count comics per user
    # We only count published comics (title IS NOT NULL)
    query = db.query(User, func.count(Comic.id).label("comic_count"))\
              .join(Comic, User.id_users == Comic.user_id)\
              .filter(Comic.title.isnot(None))\
              .group_by(User.id_users)\
              .order_by(desc("comic_count"))
              
    # Manual pagination for aggregation query
    total = query.count()
    results = query.offset((page - 1) * limit).limit(limit).all()
    
    # Format data manually as we don't have a specific Creator Schema ready here
    data = []
    for user, count in results:
        data.append({
            "id": user.id_users,
            "full_name": user.full_name,
            "username": user.username,
            "profile_photo_path": user.profile_photo_path,
            "comic_count": count
        })
        
    return paginated_response(data, page, limit, total)
