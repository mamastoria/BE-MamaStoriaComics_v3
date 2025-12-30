"""
Comics API endpoints
Comic CRUD operations, draft generation, publishing
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
import logging
from typing import Optional, List, Dict
from pydantic import BaseModel

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
logger = logging.getLogger(__name__)


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
    comic = db.query(Comic).options(
        joinedload(Comic.user),
        joinedload(Comic.panels)
    ).filter(Comic.id == comic_id).first()
    
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
    
    Returns created comic with ID and auto-queues AI generation
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
        
        # AUTO-QUEUE AI GENERATION
        # This triggers the AI to start generating the draft immediately
        task_error = None
        try:
            from app.services.task_queue_service import get_task_service
            task_service = get_task_service()
            
            # Get style name from DB
            from app.models.master_data import Style
            style = db.query(Style).filter(Style.id == story_data.style_id).first()
            style_name = style.name if style else "manga"
            
            task_name = task_service.send_generate_comic_task(
                job_id=str(comic.id),
                story=story_data.story_idea,
                style_id=style_name,
                nuances=[],  # TODO: map genre_ids to nuance names if needed
                pages=story_data.page_count or 2
            )
            
            # Update status to queued
            comic.draft_job_status = "queued"
            db.commit()
            db.refresh(comic)
            
            logger.info(f"Comic {comic.id} queued for generation: {task_name}")
            
        except Exception as e:
            # If task queue fails, run directly in background thread as fallback
            logger.warning(f"Cloud Tasks failed for comic {comic.id}: {e}. Using direct processing fallback.")
            task_error = str(e)
            
            # Start background thread for direct processing
            import threading
            import sys
            from pathlib import Path
            
            ROOT_DIR = Path(__file__).resolve().parent.parent.parent
            if str(ROOT_DIR) not in sys.path:
                sys.path.append(str(ROOT_DIR))
            
            def process_comic_directly(comic_id: int, story: str, style_name: str):
                """Background thread to process comic directly"""
                try:
                    import core
                    from app.core.database import get_session_local
                    
                    # Create new DB session for this thread
                    SessionLocal = get_session_local()
                    thread_db = SessionLocal()
                    try:
                        comic_record = thread_db.query(Comic).filter(Comic.id == comic_id).first()
                        if not comic_record:
                            logger.error(f"Direct processing: Comic {comic_id} not found")
                            return
                        
                        # Update status to PROCESSING
                        comic_record.draft_job_status = "PROCESSING"
                        thread_db.commit()
                        
                        logger.info(f"Direct processing: Generating script for {comic_id}...")
                        script = core.make_two_part_script(story, style_name, [])
                        
                        logger.info(f"Direct processing: Starting render for {comic_id}...")
                        core.start_render_all_job(script, job_id=str(comic_id))
                        
                        # Wait for completion (max 15 mins)
                        import time
                        start_time = time.time()
                        timeout = 900
                        
                        while True:
                            if time.time() - start_time > timeout:
                                raise TimeoutError("Rendering timed out")
                            
                            job_state = core.get_job(str(comic_id))
                            if not job_state:
                                time.sleep(1)
                                continue
                            
                            status = job_state.get("status")
                            if status == "done":
                                logger.info(f"Direct processing: Job {comic_id} DONE.")
                                break
                            elif status == "error":
                                raise RuntimeError(f"Render failed: {job_state.get('error')}")
                            
                            time.sleep(3)
                        
                        # Populate ComicPanel table
                        from app.models.comic_panel import ComicPanel
                        
                        # Clear existing panels for this comic
                        thread_db.query(ComicPanel).filter(ComicPanel.comic_id == comic_id).delete()
                        
                        # Get job state
                        job_state = core.get_job(str(comic_id))
                        parts = [job_state.get("part1"), job_state.get("part2")]
                        
                        panel_counter = 0
                        for p_idx, part in enumerate(parts):
                            if not part: continue
                            part_no = p_idx + 1
                            
                            # Get script data for panels (description, narration, etc)
                            part_script = part.get("part", {})
                            panels_script = part_script.get("panels", [])
                            
                            # Create records
                            for i, panel_data in enumerate(panels_script):
                                # Ensure we don't index out of bounds if images missing (should verify)
                                panel = ComicPanel(
                                    comic_id=comic_id,
                                    page_number=part_no,
                                    panel_number=i+1,
                                    image_url=f"/api/preview/{comic_id}/panel/{part_no}/{i}",
                                    description=panel_data.get("description"),
                                    narration=panel_data.get("narration"),
                                    dialogues=panel_data.get("dialogues")
                                )
                                thread_db.add(panel)
                                panel_counter += 1
                        
                        logger.info(f"Direct processing: Added {panel_counter} panels to DB for {comic_id}")
                        
                        # Update to COMPLETED
                        comic_record = thread_db.query(Comic).filter(Comic.id == comic_id).first()
                        comic_record.draft_job_status = "COMPLETED"
                        comic_record.pdf_url = f"/api/pdf/{comic_id}"
                        comic_record.preview_video_url = f"/viewer/{comic_id}"
                        thread_db.commit()
                        
                        try:
                            core.ensure_job_pdf(str(comic_id))
                        except Exception as pdf_err:
                            logger.warning(f"Direct processing PDF warning: {pdf_err}")
                        
                        logger.info(f"Direct processing: Comic {comic_id} completed successfully!")
                        
                    except Exception as inner_e:
                        logger.exception(f"Direct processing failed for comic {comic_id}: {inner_e}")
                        comic_record = thread_db.query(Comic).filter(Comic.id == comic_id).first()
                        if comic_record:
                            comic_record.draft_job_status = "FAILED"
                            thread_db.commit()
                    finally:
                        thread_db.close()
                        
                except Exception as outer_e:
                    logger.exception(f"Direct processing thread error for comic {comic_id}: {outer_e}")
            
            # Start background thread
            thread = threading.Thread(
                target=process_comic_directly,
                args=(comic.id, story_data.story_idea, style_name),
                daemon=True
            )
            thread.start()
            
            # Update status to processing (background thread will update further)
            comic.draft_job_status = "PROCESSING"
            db.commit()
            db.refresh(comic)
            
            logger.info(f"Comic {comic.id} started direct processing in background thread")
        
        response_data = ComicDetail.model_validate(comic).model_dump()
        
        return {
            "ok": True,
            "message": "Comic created and queued for AI generation",
            "data": response_data,
            "generation_status": comic.draft_job_status,
            "task_error": task_error
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
    comic = db.query(Comic).options(
        joinedload(Comic.user),
        joinedload(Comic.panels)
    ).filter(Comic.id == id).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    try:
        data = ComicWithPanels.model_validate(comic).model_dump()
        return {
            "ok": True,
            "data": data
        }
    except Exception as e:
        logger.error(f"Error validating comic {id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing comic data: {str(e)}"
        )


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
            "status": comic.draft_job_status or "pending",
            "progress": 0,
            "stage": None,
            "error": None,
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
        panels = [{
            "panel_id": p.id,
            "page_number": p.page_number,
            "panel_number": p.panel_number or (i+1),
            "image_url": p.image_url,
            "description": p.description,
            "narration": p.narration,
            "dialogue": p.dialogues
        } for i, p in enumerate(comic.panels)]
    elif hasattr(comic, 'panel_images') and comic.panel_images:
        # panel_images is a JSON list of URLs
        panels = [{
            "panel_id": i+1,
            "page_number": 1,
            "panel_number": i+1,
            "image_url": url,
            "description": None,
            "narration": None,
            "dialogue": None
        } for i, url in enumerate(comic.panel_images)]
    
    # Determine status based on draft_job_status
    status_str = comic.draft_job_status or "pending"
    if status_str.upper() == "COMPLETED":
        status_str = "completed"
    elif status_str.upper() == "PROCESSING":
        status_str = "processing"
    elif status_str.upper() == "FAILED":
        status_str = "failed"
    
    return {
        "ok": True,
        "data": {
            "comic_id": comic.id,
            "title": comic.title or comic.story_idea[:50] if comic.story_idea else "Untitled",
            "status": status_str,
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
    from app.models.comic import ComicUser
    like = db.query(ComicUser).filter(
        ComicUser.comic_id == id,
        ComicUser.user_id == current_user.id_users
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
    
    from app.models.comic import ComicUser
    
    # Check if already liked
    existing = db.query(ComicUser).filter(
        ComicUser.comic_id == id,
        ComicUser.user_id == current_user.id_users
    ).first()
    
    if existing:
        return {"ok": True, "message": "Already liked"}
    
    # Create like
    like = ComicUser(comic_id=id, user_id=current_user.id_users)
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
    from app.models.comic import ComicUser
    
    like = db.query(ComicUser).filter(
        ComicUser.comic_id == id,
        ComicUser.user_id == current_user.id_users
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
            "video_url": comic.preview_video_url or None,
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
            "video_url": comic.preview_video_url or None,
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
        comic.draft_job_status = "queued"
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
        comic.draft_job_status = "pending"
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


@router.post("/comics/story-idea/transcribe", response_model=dict)
async def transcribe_story_idea(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Transcribe audio file to text for story idea
    
    - **audio**: Audio file (ogg, wav, mp3, webm, or m4a format)
    
    Returns transcribed text
    """
    import tempfile
    import os
    
    # Validate file type
    allowed_types = ["audio/ogg", "audio/wav", "audio/mpeg", "audio/mp3", "audio/webm", "audio/m4a", "audio/x-m4a", "audio/mp4"]
    content_type = audio.content_type or ""
    
    # Also check by extension for flexibility
    filename = audio.filename or ""
    allowed_extensions = [".ogg", ".wav", ".mp3", ".webm", ".m4a", ".opus"]
    file_ext = os.path.splitext(filename)[1].lower() if filename else ""
    
    if content_type not in allowed_types and file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format: {content_type or file_ext}. Allowed: ogg, wav, mp3, webm, m4a"
        )
    
    try:
        from google.cloud import speech
        
        # Read file content
        audio_content = await audio.read()
        
        if len(audio_content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Audio file is empty"
            )
        
        # Determine encoding based on file type
        encoding = speech.RecognitionConfig.AudioEncoding.OGG_OPUS
        if file_ext in [".wav"]:
            encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16
        elif file_ext in [".mp3", ".mpeg"]:
            encoding = speech.RecognitionConfig.AudioEncoding.MP3
        elif file_ext in [".webm"]:
            encoding = speech.RecognitionConfig.AudioEncoding.WEBM_OPUS
        elif file_ext in [".m4a"]:
            encoding = speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED
        
        # Create Speech-to-Text client
        client = speech.SpeechClient()
        
        # Configure recognition
        config = speech.RecognitionConfig(
            encoding=encoding,
            sample_rate_hertz=48000,  # Common for mobile recordings
            language_code="id-ID",  # Indonesian
            alternative_language_codes=["en-US"],  # Also detect English
            enable_automatic_punctuation=True,
            model="default",
        )
        
        audio_data = speech.RecognitionAudio(content=audio_content)
        
        # Perform recognition
        response = client.recognize(config=config, audio=audio_data)
        
        # Extract transcription
        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + " "
        
        transcript = transcript.strip()
        
        if not transcript:
            # Fallback: try with different sample rate
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED,
                language_code="id-ID",
                enable_automatic_punctuation=True,
            )
            response = client.recognize(config=config, audio=audio_data)
            for result in response.results:
                transcript += result.alternatives[0].transcript + " "
            transcript = transcript.strip()
        
        if not transcript:
            transcript = "(Tidak dapat mendeteksi suara. Silakan coba lagi dengan rekaman yang lebih jelas.)"
        
        logger.info(f"Transcribed audio for user {current_user.id_users}: {transcript[:50]}...")
        
        return {
            "ok": True,
            "data": {
                "storyIdeaText": transcript
            }
        }
        
    except Exception as e:
        logger.exception(f"Audio transcription failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(e)}"
        )


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


class UpdatePanelContent(BaseModel):
    """Schema for updating panel content"""
    narration: Optional[str] = None
    description: Optional[str] = None
    dialogues: Optional[List[Dict[str, str]]] = None
    

@router.put("/comics/{comic_id}/panels/{panel_id}", response_model=dict)
async def update_panel_content(
    comic_id: int,
    panel_id: int,
    panel_data: UpdatePanelContent,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update individual panel content (dialog, narration, description)
    
    - **comic_id**: Comic ID
    - **panel_id**: Panel ID
    - **narration**: Updated narration text
    - **description**: Updated description text
    - **dialogues**: Updated dialogues array [{character: "...", text: "..."}]
    """
    from app.models.comic_panel import ComicPanel
    
    # Verify comic ownership
    comic = db.query(Comic).filter(
        Comic.id == comic_id,
        Comic.user_id == current_user.id_users
    ).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found or you don't have permission"
        )
    
    # Get the panel
    panel = db.query(ComicPanel).filter(
        ComicPanel.id == panel_id,
        ComicPanel.comic_id == comic_id
    ).first()
    
    if not panel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Panel not found"
        )
    
    # Update fields if provided
    if panel_data.narration is not None:
        panel.narration = panel_data.narration
        panel.page_narration = panel_data.narration
    
    if panel_data.description is not None:
        panel.description = panel_data.description
        panel.page_description = panel_data.description
    
    if panel_data.dialogues is not None:
        panel.dialogues = panel_data.dialogues
    
    db.commit()
    db.refresh(panel)
    
    return {
        "ok": True,
        "message": "Panel updated successfully",
        "data": {
            "panel_id": panel.id,
            "comic_id": comic_id,
            "page_number": panel.page_number,
            "panel_number": panel.panel_number,
            "narration": panel.narration,
            "description": panel.description,
            "dialogues": panel.dialogues
        }
    }


@router.post("/comics/{id}/regenerate-panel/{panel_id}", response_model=dict)
async def regenerate_panel(
    id: int,
    panel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Regenerate a specific panel with AI
    
    - **id**: Comic ID
    - **panel_id**: Panel ID to regenerate
    """
    from app.models.comic_panel import ComicPanel
    
    # Verify ownership
    comic = db.query(Comic).filter(
        Comic.id == id,
        Comic.user_id == current_user.id_users
    ).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    panel = db.query(ComicPanel).filter(
        ComicPanel.id == panel_id,
        ComicPanel.comic_id == id
    ).first()
    
    if not panel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Panel not found"
        )
    
    # TODO: Implement panel regeneration via Cloud Tasks
    # For now, return a placeholder response
    return {
        "ok": True,
        "message": "Panel regeneration queued",
        "data": {
            "comic_id": id,
            "panel_id": panel_id,
            "status": "queued"
        }
    }
