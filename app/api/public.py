"""
Public API endpoints - No authentication required
These endpoints are accessible without login for public sharing
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
import logging
from typing import Optional

from app.core.database import get_db
from app.models.comic import Comic
from app.schemas.comic import ComicWithPanels

router = APIRouter()
logger = logging.getLogger(__name__)


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
