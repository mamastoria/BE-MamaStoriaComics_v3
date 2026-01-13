"""
Job Queue API endpoints
Endpoints for triggering job processing and monitoring queue status
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from app.core.database import get_db
from app.services.job_processor import (
    process_script_jobs,
    process_image_jobs,
    process_video_jobs,
    process_all_jobs,
    get_job_queue_status
)

router = APIRouter(prefix="/api/v1/jobs", tags=["Job Queue"])
logger = logging.getLogger(__name__)


@router.post("/process/scripts")
async def trigger_script_processing(db: Session = Depends(get_db)):
    """
    Process pending script generation jobs
    
    - Picks up PENDING or SCRIPT_FAILED comics
    - Generates script using AI
    - Max 4 jobs in parallel
    """
    try:
        result = process_script_jobs(db)
        return {
            "ok": True,
            "message": "Script job processing completed",
            "data": result
        }
    except Exception as e:
        logger.error(f"Script processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process/images")
async def trigger_image_processing(db: Session = Depends(get_db)):
    """
    Process pending image generation jobs
    
    - Picks up SCRIPT_READY comics with no cover_url
    - Renders images and crops panels
    - Max 4 jobs in parallel
    """
    try:
        result = process_image_jobs(db)
        return {
            "ok": True,
            "message": "Image job processing completed",
            "data": result
        }
    except Exception as e:
        logger.error(f"Image processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process/videos")
async def trigger_video_processing(db: Session = Depends(get_db)):
    """
    Process pending video generation jobs
    
    - Picks up PROCESSING comics with cover_url but no video_url
    - Generates video from panels
    - Only 1 job at a time for stability
    """
    try:
        result = process_video_jobs(db)
        return {
            "ok": True,
            "message": "Video job processing completed",
            "data": result
        }
    except Exception as e:
        logger.error(f"Video processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process/all")
async def trigger_all_processing(db: Session = Depends(get_db)):
    """
    Process all pending jobs (scripts, images, videos)
    
    This is the main endpoint to be called by cron/scheduler
    """
    try:
        result = process_all_jobs(db)
        return {
            "ok": True,
            "message": "All job processing completed",
            "data": result
        }
    except Exception as e:
        logger.error(f"Job processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_queue_status(db: Session = Depends(get_db)):
    """
    Get current job queue status
    
    Returns counts of pending jobs by type
    """
    try:
        status = get_job_queue_status(db)
        return {
            "ok": True,
            "data": status
        }
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/locked")
async def get_locked_jobs(db: Session = Depends(get_db)):
    """
    Get list of currently locked jobs
    """
    from app.models.comic import Comic
    from sqlalchemy import text
    
    locked = db.query(Comic).filter(
        Comic.locked_by.isnot(None)
    ).all()
    
    return {
        "ok": True,
        "count": len(locked),
        "jobs": [{
            "id": c.id,
            "status": c.draft_job_status,
            "locked_by": c.locked_by,
            "locked_at": str(c.locked_at) if c.locked_at else None,
            "video_started_at": str(c.video_started_at) if c.video_started_at else None
        } for c in locked]
    }


@router.get("/stats")
async def get_status_breakdown(db: Session = Depends(get_db)):
    """
    Get breakdown of all comic statuses
    """
    from app.models.comic import Comic
    from sqlalchemy import func
    
    # Count by status
    status_counts = db.query(
        Comic.draft_job_status, 
        func.count(Comic.id)
    ).group_by(Comic.draft_job_status).all()
    
    # Count videos
    video_done = db.query(Comic).filter(Comic.preview_video_url.isnot(None)).count()
    video_pending = db.query(Comic).filter(
        Comic.preview_video_url.is_(None),
        Comic.cover_url.isnot(None)
    ).count()
    
    return {
        "ok": True,
        "status_breakdown": {s: c for s, c in status_counts},
        "video_stats": {
            "completed": video_done,
            "pending": video_pending
        },
        "total_comics": sum(c for _, c in status_counts)
    }


@router.get("/debug/{comic_id}")
async def debug_comic(comic_id: int, db: Session = Depends(get_db)):
    """
    Get raw comic data for debugging purposes
    """
    from app.models.comic import Comic
    
    comic = db.get(Comic, comic_id)
    if not comic:
        raise HTTPException(status_code=404, detail="Comic not found")
        
    # Get panels payload
    from app.models.comic_panel import ComicPanel
    panels = db.query(ComicPanel).filter(
        ComicPanel.comic_id == comic.id,
        ComicPanel.image_url.isnot(None)
    ).order_by(ComicPanel.page_number, ComicPanel.panel_number).all()
    
    panels_data = [{
        "image_url": p.image_url,
        "narration": p.narration or p.page_narration or "",
        "dialogue": p.dialogues or [],
        "description": p.description or p.page_description or ""
    } for p in panels]
    
    payload = {
        "comic_id": comic.id,
        "panels": panels_data
    }
        
    return {
        "id": comic.id,
        "payload": payload,
        "draft_job_status": comic.draft_job_status,
        "locked_by": comic.locked_by,
        "locked_at": str(comic.locked_at) if comic.locked_at else None,
        "script_started_at": str(comic.script_started_at) if comic.script_started_at else None,
        "script_completed_at": str(comic.script_completed_at) if comic.script_completed_at else None,
        "render_started_at": str(comic.render_started_at) if comic.render_started_at else None,
        "render_completed_at": str(comic.render_completed_at) if comic.render_completed_at else None,
        "video_started_at": str(comic.video_started_at) if comic.video_started_at else None,
        "video_completed_at": str(comic.video_completed_at) if comic.video_completed_at else None,
        "preview_video_url": comic.preview_video_url,
        "cover_url": comic.cover_url,
        "script_retry_count": comic.script_retry_count,
        "image_retry_count": comic.image_retry_count,
        "video_retry_count": comic.video_retry_count,
        "last_error_message": comic.last_error_message,
        "last_error_at": str(comic.last_error_at) if comic.last_error_at else None
    }


@router.get("/health")
async def job_health():
    """
    Health check for job processor
    """
    return {
        "ok": True,
        "status": "healthy",
        "service": "job-processor"
    }


@router.post("/migrate")
async def run_migration(db: Session = Depends(get_db)):
    """
    Run database migration to add job queue columns
    
    This adds the new columns needed for the job queue system
    """
    from sqlalchemy import text
    
    results = []
    
    # Columns to add
    columns = [
        ("script_retry_count", "INTEGER DEFAULT 0"),
        ("image_retry_count", "INTEGER DEFAULT 0"),
        ("video_retry_count", "INTEGER DEFAULT 0"),
        ("last_error_message", "TEXT"),
        ("last_error_at", "TIMESTAMP WITH TIME ZONE"),
        ("locked_by", "VARCHAR(100)"),
        ("locked_at", "TIMESTAMP WITH TIME ZONE"),
        ("script_started_at", "TIMESTAMP WITH TIME ZONE"),
        ("script_completed_at", "TIMESTAMP WITH TIME ZONE"),
        ("render_started_at", "TIMESTAMP WITH TIME ZONE"),
        ("render_completed_at", "TIMESTAMP WITH TIME ZONE"),
        ("clipping_started_at", "TIMESTAMP WITH TIME ZONE"),
        ("clipping_completed_at", "TIMESTAMP WITH TIME ZONE"),
        ("video_started_at", "TIMESTAMP WITH TIME ZONE"),
        ("video_completed_at", "TIMESTAMP WITH TIME ZONE"),
    ]
    
    try:
        for col_name, col_type in columns:
            try:
                sql = f"ALTER TABLE comics ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                db.execute(text(sql))
                results.append({"column": col_name, "status": "added"})
            except Exception as e:
                if "already exists" in str(e).lower():
                    results.append({"column": col_name, "status": "exists"})
                else:
                    results.append({"column": col_name, "status": "error", "error": str(e)[:100]})
        
        db.commit()
        
        return {
            "ok": True,
            "message": "Migration completed",
            "columns": results
        }
    except Exception as e:
        logger.error(f"Migration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fix-stuck")
async def fix_stuck_jobs(db: Session = Depends(get_db)):
    """
    Fix stuck jobs:
    1. Reset RENDERING jobs back to SCRIPT_READY (they failed during image gen)
    2. Clear zombie locks (locked > 30 minutes ago)
    """
    from app.models.comic import Comic
    from datetime import datetime, timedelta
    
    results = {
        "rendering_reset": 0,
        "locks_cleared": 0,
        "details": []
    }
    
    # 1. Reset RENDERING jobs to SCRIPT_READY
    rendering_jobs = db.query(Comic).filter(
        Comic.draft_job_status == 'RENDERING'
    ).all()
    
    for comic in rendering_jobs:
        comic.draft_job_status = 'SCRIPT_READY'
        comic.locked_by = None
        comic.locked_at = None
        comic.render_started_at = None
        comic.render_completed_at = None
        results["rendering_reset"] += 1
        results["details"].append(f"Reset comic #{comic.id} from RENDERING to SCRIPT_READY")
    
    # 2. Clear zombie locks (locked > 30 minutes ago)
    from datetime import timezone
    lock_timeout = datetime.now(timezone.utc) - timedelta(minutes=30)
    zombie_locks = db.query(Comic).filter(
        Comic.locked_by.isnot(None),
        Comic.locked_at < lock_timeout
    ).all()
    
    for comic in zombie_locks:
        old_lock = comic.locked_by
        comic.locked_by = None
        comic.locked_at = None
        results["locks_cleared"] += 1
        results["details"].append(f"Cleared zombie lock on comic #{comic.id} (was: {old_lock})")
    
    db.commit()
    
    return {
        "ok": True,
        "message": f"Fixed {results['rendering_reset']} stuck renders, cleared {results['locks_cleared']} zombie locks",
        "data": results
    }


@router.post("/clear-all-locks")
async def clear_all_locks(db: Session = Depends(get_db)):
    """
    EMERGENCY: Force clear ALL locks regardless of age.
    Use this when the queue is completely stuck.
    """
    from app.models.comic import Comic
    
    locked_jobs = db.query(Comic).filter(
        Comic.locked_by.isnot(None)
    ).all()
    
    count = 0
    details = []
    for comic in locked_jobs:
        old_lock = comic.locked_by
        comic.locked_by = None
        comic.locked_at = None
        count += 1
        details.append(f"Cleared lock on comic #{comic.id} (was: {old_lock})")
    
    db.commit()
    
    return {
        "ok": True,
        "message": f"Force cleared {count} locks",
        "count": count,
        "details": details
    }

