"""
Comics API endpoints
Comic CRUD operations, draft generation, publishing
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_optional_user
from app.models.user import User
from app.models.comic import Comic
from app.schemas.comic import (
    CreateStoryIdea,
    UpdateSummary,
    UpdateCharacter,
    UpdateBackgrounds,
    PublishComic,
    ComicListItem,
    ComicDetail,
    ComicWithPanels,
    DraftStatus
)
from app.services.comic_service import ComicService
from app.utils.pagination import paginate, get_pagination_params
from app.utils.responses import paginated_response

router = APIRouter()


@router.get("/comics", response_model=dict)
async def list_comics(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    genre: Optional[str] = None,
    style: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all published comics with pagination
    
    - **page**: Page number (default: 1)
    - **per_page**: Items per page (default: 20, max: 100)
    - **genre**: Filter by genre name
    - **style**: Filter by style name
    - **search**: Search in title and synopsis
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
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Comic.title.ilike(search_term)) | 
            (Comic.synopsis.ilike(search_term))
        )
    
    # Order by views (most popular first)
    query = query.order_by(Comic.total_views.desc())
    
    # Paginate
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)
    
    # Convert to schema
    comics_data = [ComicListItem.model_validate(comic).model_dump() for comic in items]
    
    return paginated_response(comics_data, page, per_page, total)


@router.get("/comics/show/{comic_id}", response_model=dict)
async def get_comic_detail(
    comic_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get comic detail by ID
    
    - **comic_id**: Comic ID
    
    Returns complete comic information including panels
    """
    comic = db.query(Comic).filter(Comic.id == comic_id).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Track view
    ComicService.track_comic_read(db, comic, current_user)
    
    return {
        "ok": True,
        "data": ComicWithPanels.model_validate(comic).model_dump()
    }


@router.post("/comics/story-idea", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_story_and_attributes(
    story_data: CreateStoryIdea,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new comic from story idea (Step 1)
    
    - **story_idea**: Story idea text or transcribed audio
    - **page_count**: Number of pages (1-25)
    - **genre_ids**: List of genre IDs
    - **style_id**: Style ID
    
    Returns created comic with ID
    """
    try:
        comic = ComicService.create_comic_from_story_idea(
            db=db,
            user=current_user,
            story_idea=story_data.story_idea,
            page_count=story_data.page_count,
            genre_ids=story_data.genre_ids,
            style_id=story_data.style_id
        )
        
        return {
            "ok": True,
            "message": "Comic created successfully",
            "data": ComicDetail.model_validate(comic).model_dump()
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{comic}/summary", response_model=dict)
async def update_comic_summary(
    comic: int,
    summary_data: UpdateSummary,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update comic summary
    
    - **comic**: Comic ID
    - **summary**: New summary text
    """
    comic_obj = db.query(Comic).filter(
        Comic.id == comic,
        Comic.user_id == current_user.id_users
    ).first()
    
    if not comic_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found or you don't have permission"
        )
    
    updated_comic = ComicService.update_comic_summary(
        db=db,
        comic=comic_obj,
        summary=summary_data.summary
    )
    
    return {
        "ok": True,
        "message": "Summary updated successfully",
        "data": ComicDetail.model_validate(updated_comic).model_dump()
    }


@router.put("/comics/{comic}/characters", response_model=dict)
async def update_comic_character(
    comic: int,
    character_data: UpdateCharacter,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update comic character selection (Step 2)
    
    - **comic**: Comic ID
    - **character_key**: Selected character key/ID
    """
    comic_obj = db.query(Comic).filter(
        Comic.id == comic,
        Comic.user_id == current_user.id_users
    ).first()
    
    if not comic_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found or you don't have permission"
        )
    
    updated_comic = ComicService.update_comic_character(
        db=db,
        comic=comic_obj,
        character_key=character_data.character_key
    )
    
    return {
        "ok": True,
        "message": "Character updated successfully",
        "data": ComicDetail.model_validate(updated_comic).model_dump()
    }


@router.put("/comics/{comic}/backgrounds", response_model=dict)
async def update_comic_backgrounds(
    comic: int,
    backgrounds_data: UpdateBackgrounds,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update comic background selection (Step 3)
    
    - **comic**: Comic ID
    - **background_ids**: List of background IDs
    """
    comic_obj = db.query(Comic).filter(
        Comic.id == comic,
        Comic.user_id == current_user.id_users
    ).first()
    
    if not comic_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found or you don't have permission"
        )
    
    try:
        updated_comic = ComicService.update_comic_backgrounds(
            db=db,
            comic=comic_obj,
            background_ids=backgrounds_data.background_ids
        )
        
        return {
            "ok": True,
            "message": "Backgrounds updated successfully",
            "data": ComicDetail.model_validate(updated_comic).model_dump()
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/comics/drafts", response_model=dict)
async def list_drafts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List user's draft comics
    
    - **page**: Page number
    - **per_page**: Items per page
    
    Returns list of user's unpublished comics
    """
    query = db.query(Comic).filter(
        Comic.user_id == current_user.id_users,
        Comic.title.is_(None)  # Drafts don't have title yet
    ).order_by(Comic.updated_at.desc())
    
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)
    
    comics_data = [ComicDetail.model_validate(comic).model_dump() for comic in items]
    
    return paginated_response(comics_data, page, per_page, total)


@router.post("/comics/{comic}/publish", response_model=dict)
async def publish_comic(
    comic: int,
    publish_data: PublishComic,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Publish comic (make it public)
    
    - **comic**: Comic ID
    - **title**: Optional custom title
    - **synopsis**: Optional custom synopsis
    """
    comic_obj = db.query(Comic).filter(
        Comic.id == comic,
        Comic.user_id == current_user.id_users
    ).first()
    
    if not comic_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found or you don't have permission"
        )
    
    published_comic = ComicService.publish_comic(
        db=db,
        comic=comic_obj,
        title=publish_data.title,
        synopsis=publish_data.synopsis
    )
    
    return {
        "ok": True,
        "message": "Comic published successfully",
        "data": ComicDetail.model_validate(published_comic).model_dump()
    }


@router.post("/comics/{id}/track-read", response_model=dict)
async def track_read(
    id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Track comic read/view
    
    - **id**: Comic ID
    
    Increments view count and adds to user's read history if logged in
    """
    comic = db.query(Comic).filter(Comic.id == id).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    ComicService.track_comic_read(db, comic, current_user)
    
    return {
        "ok": True,
        "message": "Read tracked successfully"
    }


@router.get("/comics/{comic}/similar", response_model=dict)
async def get_similar_comics(
    comic: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get similar comics based on genre and style
    
    - **comic**: Comic ID
    - **limit**: Number of similar comics (max: 50)
    """
    comic_obj = db.query(Comic).filter(Comic.id == comic).first()
    
    if not comic_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    similar = ComicService.get_similar_comics(db, comic_obj, limit)
    similar_data = [ComicListItem.model_validate(c).model_dump() for c in similar]
    
    return {
        "ok": True,
        "data": similar_data
    }


# ============================================================
# Additional endpoints for frontend compatibility
# ============================================================

@router.get("/comics/{id}", response_model=dict)
async def get_comic_by_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get comic detail by ID (alternative endpoint)
    """
    comic = db.query(Comic).filter(Comic.id == id).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    return {
        "ok": True,
        "data": ComicWithPanels.model_validate(comic).model_dump()
    }


@router.get("/comics/{id}/draft/status", response_model=dict)
async def get_draft_status(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comic draft status
    
    Returns current generation status: pending, processing, completed, failed
    """
    comic = db.query(Comic).filter(
        Comic.id == id,
        Comic.user_id == current_user.id_users
    ).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    return {
        "ok": True,
        "data": {
            "id": comic.id,
            "status": comic.status or "pending",
            "progress": comic.generation_progress or 0,
            "stage": comic.generation_stage or None,
            "error": comic.generation_error or None,
            "created_at": comic.created_at.isoformat() if comic.created_at else None,
            "updated_at": comic.updated_at.isoformat() if comic.updated_at else None
        }
    }


@router.get("/comics/{id}/panels", response_model=dict)
async def get_comic_panels(
    id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get all panels for a comic
    """
    comic = db.query(Comic).filter(Comic.id == id).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Get panels from relationship or generate from stored data
    panels = []
    if hasattr(comic, 'panels') and comic.panels:
        panels = [{"panel_number": i+1, "image_url": p.image_url, "dialogue": p.dialogue} 
                  for i, p in enumerate(comic.panels)]
    elif comic.panel_images:
        # panel_images is a JSON list of URLs
        panels = [{"panel_number": i+1, "image_url": url} 
                  for i, url in enumerate(comic.panel_images)]
    
    return {
        "ok": True,
        "data": {
            "comic_id": comic.id,
            "total_panels": len(panels),
            "panels": panels
        }
    }


@router.get("/comics/{id}/likes/status", response_model=dict)
async def get_like_status(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if current user has liked this comic
    """
    comic = db.query(Comic).filter(Comic.id == id).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Check if user has liked
    from app.models.like import Like
    like = db.query(Like).filter(
        Like.comic_id == id,
        Like.user_id == current_user.id_users
    ).first()
    
    return {
        "ok": True,
        "data": {
            "comic_id": id,
            "is_liked": like is not None,
            "total_likes": comic.total_likes or 0
        }
    }


@router.post("/comics/{id}/likes", response_model=dict)
async def like_comic(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Like a comic
    """
    comic = db.query(Comic).filter(Comic.id == id).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    from app.models.like import Like
    
    # Check if already liked
    existing = db.query(Like).filter(
        Like.comic_id == id,
        Like.user_id == current_user.id_users
    ).first()
    
    if existing:
        return {"ok": True, "message": "Already liked"}
    
    # Create like
    like = Like(comic_id=id, user_id=current_user.id_users)
    db.add(like)
    
    # Increment counter
    comic.total_likes = (comic.total_likes or 0) + 1
    db.commit()
    
    return {"ok": True, "message": "Comic liked successfully"}


@router.delete("/comics/{id}/likes", response_model=dict)
async def unlike_comic(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unlike a comic
    """
    from app.models.like import Like
    
    like = db.query(Like).filter(
        Like.comic_id == id,
        Like.user_id == current_user.id_users
    ).first()
    
    if not like:
        return {"ok": True, "message": "Not liked"}
    
    db.delete(like)
    
    # Decrement counter
    comic = db.query(Comic).filter(Comic.id == id).first()
    if comic:
        comic.total_likes = max(0, (comic.total_likes or 0) - 1)
    
    db.commit()
    
    return {"ok": True, "message": "Comic unliked successfully"}


@router.get("/comics/{id}/preview-video", response_model=dict)
async def get_preview_video(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Get preview video URL for a comic
    """
    comic = db.query(Comic).filter(Comic.id == id).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    return {
        "ok": True,
        "data": {
            "comic_id": id,
            "video_url": comic.video_url or None,
            "thumbnail_url": comic.cover_url or None
        }
    }


@router.get("/comics/{id}/exported-media", response_model=dict)
async def get_exported_media(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get exported media (PDF, video) for a comic
    """
    comic = db.query(Comic).filter(Comic.id == id).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    return {
        "ok": True,
        "data": {
            "comic_id": id,
            "pdf_url": comic.pdf_url or None,
            "video_url": comic.video_url or None,
            "cover_url": comic.cover_url or None
        }
    }


@router.post("/comics/{id}/generate", response_model=dict)
async def generate_comic(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start comic generation process
    
    This will queue the comic for AI generation
    """
    comic = db.query(Comic).filter(
        Comic.id == id,
        Comic.user_id == current_user.id_users
    ).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Queue for generation
    try:
        from app.services.task_queue_service import get_task_service
        task_service = get_task_service()
        
        task_name = task_service.send_generate_comic_task(
            job_id=str(comic.id),
            story=comic.story_idea or "",
            style_id=str(comic.style_id) if comic.style_id else None,
            nuances=[],
            pages=comic.page_count or 2
        )
        
        # Update status
        comic.status = "queued"
        db.commit()
        
        return {
            "ok": True,
            "message": "Comic generation started",
            "data": {
                "comic_id": id,
                "status": "queued",
                "task_id": task_name
            }
        }
    except Exception as e:
        # Fallback: mark as pending for direct processing
        comic.status = "pending"
        db.commit()
        
        return {
            "ok": True,
            "message": "Comic queued for generation",
            "data": {
                "comic_id": id,
                "status": "pending",
                "error": str(e) if str(e) else None
            }
        }


@router.put("/comics/{comic}/character", response_model=dict)
async def update_comic_character_singular(
    comic: int,
    character_data: UpdateCharacter,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update comic character selection (singular endpoint)
    Alias for /comics/{comic}/characters
    """
    return await update_comic_character(comic, character_data, current_user, db)


@router.put("/comics/{comic}/summary", response_model=dict)
async def update_comic_summary_v2(
    comic: int,
    summary_data: UpdateSummary,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update comic summary (v2 endpoint path)
    """
    return await update_comic_summary(comic, summary_data, current_user, db)


@router.delete("/comics/drafts/{id}", response_model=dict)
async def delete_draft(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a draft comic
    """
    comic = db.query(Comic).filter(
        Comic.id == id,
        Comic.user_id == current_user.id_users
    ).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found"
        )
    
    # Only delete if not published
    if comic.title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete published comic"
        )
    
    db.delete(comic)
    db.commit()
    
    return {"ok": True, "message": "Draft deleted successfully"}

