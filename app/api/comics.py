"""
Comics API endpoints
Comic CRUD operations, draft generation, publishing
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, BackgroundTasks
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
    q: Optional[str] = None,  # Changed from 'search' to 'q'
    db: Session = Depends(get_db)
):
    """
    List all published comics with pagination
    
    - **page**: Page number (default: 1)
    - **per_page**: Items per page (default: 20, max: 100)
    - **genre**: Filter by genre name
    - **style**: Filter by style name
    - **q**: Search query in title, synopsis, and tags
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
            (Comic.tags.ilike(search_term))  # Added tags search
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
    
    Returns created comic with ID and generates SCRIPT ONLY (no images yet).
    User can review/edit the draft, then call /comics/{id}/generate to render images.
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
        
        # Get style name from DB
        from app.models.master_data import Style
        style = db.query(Style).filter(Style.id == story_data.style_id).first()
        style_name = style.name if style else "manga"
        
        # GENERATE SCRIPT ONLY (not rendering images)
        # This is fast and can be done synchronously
        script_error = None
        try:
            import sys
            from pathlib import Path
            
            ROOT_DIR = Path(__file__).resolve().parent.parent.parent
            if str(ROOT_DIR) not in sys.path:
                sys.path.append(str(ROOT_DIR))
            
            import core
            from app.models.comic_panel import ComicPanel
            
            # Update status to generating script
            comic.draft_job_status = "GENERATING_SCRIPT"
            db.commit()
            
            logger.info(f"Generating script for comic {comic.id}...")
            
            # Generate script (text only, no images)
            script = core.make_two_part_script(
                story_data.story_idea, 
                style_name, 
                []  # nuances
            )
            
            logger.info(f"Script generated for comic {comic.id}, creating draft panels...")
            
            # Clear existing panels
            db.query(ComicPanel).filter(ComicPanel.comic_id == comic.id).delete()
            
            # Save script as draft panels (no image_url yet)
            # Script format: {"global": {...}, "parts": [{"part_no": 1, ...}, {"part_no": 2, ...}]}
            panel_counter = 0
            parts = script.get("parts", [])
            
            for part in parts:
                if not part or not isinstance(part, dict):
                    continue
                part_no = int(part.get("part_no", 0))
                if part_no not in (1, 2):
                    continue
                panels_script = part.get("panels", [])
                
                for i, panel_data in enumerate(panels_script):
                    panel = ComicPanel(
                        comic_id=comic.id,
                        page_number=part_no,
                        panel_number=i + 1,
                        image_url=None,  # No image yet - will be generated on approve
                        description=panel_data.get("panel_context") or panel_data.get("description"),
                        page_description=panel_data.get("panel_context") or panel_data.get("description"),
                        narration=panel_data.get("narration"),
                        page_narration=panel_data.get("narration"),
                        dialogues=panel_data.get("dialogues", []),
                        instruksi_visual=panel_data.get("instruksi_visual"),
                        instruksi_render_teks=panel_data.get("instruksi_render_teks"),
                        main_characters_on_page=panel_data.get("main_characters_in_panel")
                    )
                    db.add(panel)
                    panel_counter += 1
            
            # Extract metadata from AI script to fill comic columns
            global_data = script.get("global", {})
            parts_data = script.get("parts", [])
            
            # Title from AI
            ai_title = (
                global_data.get("comic_title") or 
                script.get("suggested_title") or 
                script.get("title") or 
                ""
            ).strip()
            
            # Tagline/Theme
            ai_tagline = (global_data.get("tagline") or "").strip()
            
            # Characters info for keywords
            characters = global_data.get("characters", [])
            character_names = [c.get("name", "") for c in characters if isinstance(c, dict)]
            
            # Extract keywords from character names and story
            keywords_list = []
            if character_names:
                keywords_list.extend([n for n in character_names if n])
            # Add style and nuance as keywords too
            if style_name:
                keywords_list.append(style_name)
            
            # Get mood from style
            style_data = global_data.get("style", {})
            ai_mood = style_data.get("color_mood", "")
            
            # Build synopsis from part summaries
            synopsis_parts = []
            for part in parts_data:
                if isinstance(part, dict):
                    ps = (part.get("part_summary") or "").strip()
                    if ps:
                        synopsis_parts.append(ps)
            ai_synopsis = " ".join(synopsis_parts) if synopsis_parts else story_data.story_idea[:500]
            
            # Update comic with all extracted data
            comic.draft_job_status = "SCRIPT_READY"
            comic.draft_job_id = str(comic.id)  # Job ID = Comic ID
            comic.title = ai_title or story_data.story_idea[:100]  # Use title or fallback
            comic.summary = ai_title or story_data.story_idea[:100]
            comic.synopsis = ai_synopsis
            comic.theme = ai_tagline or None
            comic.keywords = keywords_list if keywords_list else None
            comic.mood = ai_mood or None
            comic.layout = "portrait"  # Default to portrait for 9-panel grid
            comic.publisher = None  # Will be set on publish
            
            # Tags from keywords (for search)
            if keywords_list:
                comic.tags = " ".join([f"#{k.lower().replace(' ', '')}" for k in keywords_list[:5]])
            
            db.commit()
            db.refresh(comic)
            
            logger.info(f"Comic {comic.id}: Script ready with {panel_counter} panels. Title: '{ai_title}'")
            
        except Exception as e:
            logger.exception(f"Script generation failed for comic {comic.id}: {e}")
            script_error = str(e)
            comic.draft_job_status = "SCRIPT_FAILED"
            db.commit()
        
        response_data = ComicDetail.model_validate(comic).model_dump()
        
        return {
            "ok": True,
            "message": "Comic draft created. Review panels and call /comics/{id}/generate when ready.",
            "data": response_data,
            "generation_status": comic.draft_job_status,
            "script_error": script_error
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
        Comic.user_id == current_user.id_users
        # Removed: Comic.title.is_(None) - now returns all comics for frontend filtering
    ).order_by(Comic.updated_at.desc())
    
    page, per_page = get_pagination_params(page, per_page)
    items, total = paginate(query, page, per_page)
    
    # Build comics data with status field for frontend filtering
    comics_data = []
    for comic in items:
        data = ComicDetail.model_validate(comic).model_dump()
        # Add status field based on draft_job_status (UPPERCASE for frontend)
        data['status'] = (comic.draft_job_status or 'PENDING').upper()
        # Ensure coverUrl mapping (frontend uses camelCase)
        data['coverUrl'] = comic.cover_url
        comics_data.append(data)
    
    total_pages = (total + per_page - 1) // per_page

    
    # Custom response format matching frontend expectations
    return {
        "ok": True,
        "data": {
            "drafts": comics_data,
            "pagination": {
                "current_page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    }


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
    Get comic draft status with full draft data
    
    Returns current generation status AND full draft content for editing
    """
    comic = db.query(Comic).options(
        joinedload(Comic.panels)
    ).filter(
        Comic.id == id,
        Comic.user_id == current_user.id_users
    ).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Map draft_job_status to frontend JobStatus enum
    status_map = {
        "QUEUED": "idle",
        "PENDING": "idle", 
        "GENERATING_SCRIPT": "processing",
        "SCRIPT_READY": "idle",  # Script done, waiting for user to approve
        "PROCESSING": "processing",
        "RENDERING": "processing",
        "COMPLETED": "completed",
        "FAILED": "failed",
        "SCRIPT_FAILED": "failed",
    }
    raw_status = comic.draft_job_status or "pending"
    frontend_status = status_map.get(raw_status.upper(), raw_status.lower())
    
    # Build panels list for frontend
    panels_data = []
    if comic.panels:
        for i, p in enumerate(comic.panels):
            panels_data.append({
                "panel_id": p.id,
                "page_number": p.page_number,
                "panel_number": p.panel_number or (i + 1),
                "image_url": p.image_url,
                "description": p.description,
                "narration": p.narration,
                "dialogue": p.dialogues
            })
    
    # Build detailed summary from panels (title + all narrations + dialogues)
    summary_parts = []
    if comic.title:
        summary_parts.append(f"**{comic.title}**\n")
    if comic.synopsis:
        summary_parts.append(comic.synopsis + "\n")
    
    # Add narration/dialogue from each panel
    if comic.panels:
        for p in comic.panels:
            panel_text = []
            if p.narration:
                panel_text.append(f"[Panel {p.page_number}-{p.panel_number}] {p.narration}")
            if p.dialogues:
                for dlg in p.dialogues:
                    if isinstance(dlg, str):
                        panel_text.append(f"  💬 {dlg}")
                    elif isinstance(dlg, dict):
                        char = dlg.get("character", dlg.get("name", ""))
                        text = dlg.get("text", dlg.get("dialog", ""))
                        panel_text.append(f"  💬 {char}: {text}")
            if panel_text:
                summary_parts.append("\n".join(panel_text))
    
    detailed_summary = "\n\n".join(summary_parts) if summary_parts else (comic.story_idea[:500] if comic.story_idea else "")
    
    # Build genre list with proper structure
    genres_data = []
    if comic.genre and isinstance(comic.genre, list):
        for i, g in enumerate(comic.genre):
            if isinstance(g, str):
                genres_data.append({"id": i + 1, "name": g})
            elif isinstance(g, dict):
                genres_data.append({"id": g.get("id", i + 1), "name": g.get("name", str(g))})
    
    return {
        "ok": True,
        "data": {
            "id": comic.id,
            "status": raw_status.upper(),  # Return actual status like SCRIPT_READY
            "summary": detailed_summary,
            "title": comic.title,
            "page_count": comic.page_count,  # snake_case for frontend
            "draft_job_id": comic.draft_job_id,  # snake_case for frontend
            "is_ready_to_generate": raw_status.upper() == "SCRIPT_READY",  # snake_case
            "panels": panels_data,
            "style": {"id": 1, "name": comic.style} if comic.style else None,
            "character": None,  # TODO: Add character data
            "genres": genres_data,
            "backgrounds": [],  # TODO: Add backgrounds data
            "progress": 0,
            "stage": raw_status,
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
        
        # Ensure proper order: page_number first, then panel_number
        panels = sorted(panels, key=lambda x: (x.get('page_number', 0) or 0, x.get('panel_number', 0) or 0))
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
    
    # Determine status based on draft_job_status - must be UPPERCASE for Flutter
    status_str = (comic.draft_job_status or "PENDING").upper()
    # Map to standard statuses
    status_mapping = {
        "COMPLETED": "COMPLETED",
        "PROCESSING": "PROCESSING",
        "RENDERING": "RENDERING",
        "FAILED": "FAILED",
        "SCRIPT_READY": "SCRIPT_READY",
        "GENERATING_SCRIPT": "GENERATING_SCRIPT",
    }
    status_str = status_mapping.get(status_str, status_str)
    
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
            "title": comic.title or "Untitled",
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
    Start comic IMAGE generation from approved draft
    
    This takes the user-edited draft panels and renders actual images.
    Should only be called after user has reviewed and approved the draft.
    """
    from app.models.comic_panel import ComicPanel
    import threading
    from app.services.comic_renderer import render_comic_images_task
    
    comic = db.query(Comic).filter(
        Comic.id == id,
        Comic.user_id == current_user.id_users
    ).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Check if already processing
    if comic.draft_job_status in ["PROCESSING", "RENDERING"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Comic is already being processed"
        )
    
    # Get draft panels from DB
    panels = db.query(ComicPanel).filter(
        ComicPanel.comic_id == id
    ).order_by(ComicPanel.page_number, ComicPanel.panel_number).all()
    
    if not panels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No draft panels found. Create a story idea first."
        )
    
    # Reconstruct script from DB panels for rendering
    # Group panels by page_number (part)
    from collections import defaultdict
    parts_dict = defaultdict(list)
    for panel in panels:
        parts_dict[panel.page_number].append({
            "panel_no": panel.panel_number,
            "panel_idx": panel.panel_number - 1,
            "panel_title": f"Panel {panel.page_number}-{panel.panel_number}",
            "panel_context": panel.description or panel.page_description or "",
            "description": panel.description or panel.page_description,
            "narration": panel.narration or panel.page_narration or "",
            "dialogues": panel.dialogues or [],
            "instruksi_visual": panel.instruksi_visual,
            "instruksi_render_teks": panel.instruksi_render_teks,
            "main_characters_in_panel": panel.main_characters_on_page
        })
    
    # Build script structure expected by core.start_render_all_job
    script = {
        "parts": [],
        "global": {
            "comic_title": comic.title or "Untitled"
        }
    }
    
    for part_no in sorted(parts_dict.keys()):
        script["parts"].append({
            "part_no": part_no,
            "panels": parts_dict[part_no]
        })
    
    # Get style name - Comic stores style as string directly, not as FK
    style_name = comic.style or "manga"
    
    # Update status to RENDERING
    comic.draft_job_status = "RENDERING"
    db.commit()
    
    # Start background thread using service
    thread = threading.Thread(
        target=render_comic_images_task,
        args=(comic.id, script, style_name),
        daemon=True
    )
    thread.start()
    
    return {
        "ok": True,
        "message": "Comic image generation started",
        "data": {
            "comic_id": id,
            "status": "RENDERING",
            "panels_count": len(panels)
        }
    }


@router.post("/comics/{id}/generate-video", response_model=dict)
async def generate_comic_video(
    id: int,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate cinematic video from comic panels with narration.
    
    Features:
    - Ken Burns effect (zoom/pan animation)
    - Fade transitions between panels
    - TTS narration in Indonesian
    - 9:16 vertical format for mobile
    - Cinematic letterbox bars
    
    The video URL will be stored in comic.preview_video_url when complete.
    """
    from app.models.comic_panel import ComicPanel
    
    comic = db.query(Comic).filter(
        Comic.id == id,
        Comic.user_id == current_user.id_users
    ).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Get panels
    panels = db.query(ComicPanel).filter(
        ComicPanel.comic_id == id
    ).order_by(ComicPanel.page_number, ComicPanel.panel_number).all()
    
    if not panels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No panels found. Generate comic images first."
        )
    
    # Check if panels have images
    panels_with_images = [p for p in panels if p.image_url]
    if not panels_with_images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Panels don't have images yet. Wait for image generation to complete."
        )
    
    # Prepare panel data for video generator
    panel_data = []
    for p in panels_with_images:
        panel_data.append({
            "image_url": p.image_url,
            "narration": p.narration or p.page_narration or "",
            "dialogue": p.dialogues or [],
            "description": p.description or p.page_description or ""
        })
    
    # Start video generation in background
    def generate_video_task(comic_id: int, panels_data: list):
        """Background task to generate video"""
        try:
            import sys
            import traceback
            from pathlib import Path
            
            ROOT_DIR = Path(__file__).resolve().parent.parent.parent
            if str(ROOT_DIR) not in sys.path:
                sys.path.append(str(ROOT_DIR))
            
            from app.core.database import get_session_local
            import video_generator
            
            SessionLocal = get_session_local()
            thread_db = SessionLocal()
            
            try:
                logger.info(f"Starting cinematic video generation for comic {comic_id}...")
                logger.info(f"Panels data count: {len(panels_data)}")
                
                # Generate video - this function handles GCS upload internally
                video_url = video_generator.generate_video_for_comic(
                    comic_id=comic_id,
                    panels=panels_data
                )
                
                if video_url:
                    logger.info(f"Video generation returned URL: {video_url}")
                    
                    # Update comic with video URL
                    comic_record = thread_db.query(Comic).filter(Comic.id == comic_id).first()
                    if comic_record:
                        comic_record.preview_video_url = video_url
                        thread_db.commit()
                        logger.info(f"Comic {comic_id}: Video URL saved to database")
                    
                    logger.info(f"Comic {comic_id}: Cinematic video generated successfully!")
                else:
                    logger.error(f"Video generation returned None for comic {comic_id}")
                    
            except Exception as e:
                logger.exception(f"Video generation task failed for comic {comic_id}: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
            finally:
                thread_db.close()
                
        except Exception as outer_e:
            logger.exception(f"Video generation outer error for comic {comic_id}: {outer_e}")
    
    # Run in background
    background.add_task(generate_video_task, comic.id, panel_data)
    
    return {
        "ok": True,
        "message": "Cinematic video generation started",
        "data": {
            "comic_id": id,
            "status": "VIDEO_GENERATING",
            "panels_count": len(panel_data),
            "features": [
                "Ken Burns effect (zoom/pan)",
                "Fade transitions",
                "TTS narration (Indonesian)",
                "9:16 vertical format",
                "Cinematic letterbox"
            ]
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


# ===================== DEBUG ENDPOINTS (REMOVE IN PRODUCTION) =====================

@router.post("/debug/generate-video/{comic_id}", response_model=dict)
async def debug_generate_video(
    comic_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    DEBUG ONLY: Generate video without authentication.
    This endpoint should be removed in production.
    """
    from app.models.comic_panel import ComicPanel
    
    comic = db.query(Comic).filter(Comic.id == comic_id).first()
    
    if not comic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic not found"
        )
    
    # Get panels with images
    panels = db.query(ComicPanel).filter(
        ComicPanel.comic_id == comic_id,
        ComicPanel.image_url.isnot(None)
    ).order_by(ComicPanel.page_number, ComicPanel.panel_number).all()
    
    if not panels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No panels with images found"
        )
    
    panel_data = [{
        "image_url": p.image_url,
        "narration": p.narration or p.page_narration or "",
        "dialogue": p.dialogues or [],
        "description": p.description or p.page_description or ""
    } for p in panels]
    
    # Background task for video generation
    def debug_video_task(cid: int, pdata: list):
        try:
            import sys
            import traceback
            from pathlib import Path
            
            ROOT_DIR = Path(__file__).resolve().parent.parent.parent
            if str(ROOT_DIR) not in sys.path:
                sys.path.append(str(ROOT_DIR))
            
            from app.core.database import get_session_local
            import video_generator
            
            SessionLocal = get_session_local()
            thread_db = SessionLocal()
            
            try:
                logger.info(f"[DEBUG] Starting video generation for comic {cid}...")
                logger.info(f"[DEBUG] Panel count: {len(pdata)}")
                
                video_url = video_generator.generate_video_for_comic(
                    comic_id=cid,
                    panels=pdata
                )
                
                logger.info(f"[DEBUG] Video generation returned: {video_url}")
                
                if video_url:
                    comic_rec = thread_db.query(Comic).filter(Comic.id == cid).first()
                    if comic_rec:
                        comic_rec.preview_video_url = video_url
                        thread_db.commit()
                        logger.info(f"[DEBUG] Video URL saved: {video_url}")
                else:
                    logger.error(f"[DEBUG] Video generation returned None!")
                    
            except Exception as e:
                logger.exception(f"[DEBUG] Video generation failed: {e}")
                logger.error(f"[DEBUG] Traceback: {traceback.format_exc()}")
            finally:
                thread_db.close()
        except Exception as outer:
            logger.exception(f"[DEBUG] Outer error: {outer}")
    
    background.add_task(debug_video_task, comic_id, panel_data)
    
    return {
        "ok": True,
        "message": "[DEBUG] Video generation started",
        "data": {
            "comic_id": comic_id,
            "panels_count": len(panel_data),
            "first_panel_image": panel_data[0].get("image_url") if panel_data else None
        }
    }

@router.get("/debug/ffmpeg", response_model=dict)
async def debug_ffmpeg():
    """Check FFmpeg installation and codecs"""
    import subprocess
    import shutil
    
    ffmpeg_path = shutil.which("ffmpeg")
    version_out = ""
    encoders_out = ""
    
    if ffmpeg_path:
        try:
            version_out = subprocess.check_output([ffmpeg_path, "-version"], text=True, stderr=subprocess.STDOUT)
            encoders_out = subprocess.check_output([ffmpeg_path, "-encoders"], text=True, stderr=subprocess.STDOUT)
            
            # Check specifically for libx264
            has_libx264 = "libx264" in encoders_out
        except Exception as e:
            version_out = f"Error running ffmpeg: {e}"
    else:
        version_out = "FFmpeg binary not found in PATH"
        has_libx264 = False

    return {
        "path": ffmpeg_path,
        "has_libx264": has_libx264,
        "version_head": version_out[:500],
        "encoders_head": encoders_out[:1000] if encoders_out else ""
    }

@router.get("/debug/check-video/{comic_id}", response_model=dict)
async def debug_check_video(
    comic_id: int,
    db: Session = Depends(get_db)
):
    """Check comic video status"""
    comic = db.query(Comic).filter(Comic.id == comic_id).first()
    if not comic:
        return {"error": "Comic not found"}
    
    return {
        "id": comic.id,
        "title": comic.title,
        "preview_video_url": comic.preview_video_url
    }
