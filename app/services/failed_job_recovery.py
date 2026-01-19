"""
Failed Job Recovery Service
Automatically recovers comics stuck in FAILED status
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.comic import Comic
from app.models.comic_panel import ComicPanel

logger = logging.getLogger(__name__)

# Recovery configuration
RECOVERY_CONFIG = {
    "min_retry_delay_minutes": 5,  # Wait at least 5 minutes before retry
    "max_retries": 3,  # Maximum retry attempts before giving up
}


def get_failed_comics_for_recovery(db: Session, limit: int = 10) -> List[Comic]:
    """
    Get comics with FAILED status that can be recovered
    AND comics stuck in RENDERING but might be done
    
    Conditions:
    1. Status = FAILED
    2. Status = RENDERING but stuck for > 30 mins
    """
    min_delay = timedelta(minutes=RECOVERY_CONFIG["min_retry_delay_minutes"])
    retry_threshold = datetime.now() - min_delay
    max_retries = RECOVERY_CONFIG["max_retries"]
    
    # Stuck rendering check (30 mins timeout)
    stuck_rendering_threshold = datetime.now() - timedelta(minutes=30)
    
    comics = db.query(Comic).filter(
        or_(
            # Case 1: Explicit FAILED status
            and_(
                Comic.draft_job_status == 'FAILED',
                or_(
                    Comic.last_error_at.is_(None),
                    Comic.last_error_at < retry_threshold
                ),
                or_(
                    Comic.script_retry_count.is_(None),
                    Comic.script_retry_count < max_retries
                )
            ),
            # Case 2: Stuck in RENDERING (e.g. comic #330)
            and_(
                Comic.draft_job_status == 'RENDERING',
                Comic.render_started_at < stuck_rendering_threshold,
                # Ensure we don't pick up actively running jobs (check lock)
                or_(
                    Comic.locked_by.is_(None),
                    Comic.locked_at < stuck_rendering_threshold
                )
            )
        )
    ).order_by(Comic.id.asc()).limit(limit).all()
    
    return comics


def analyze_failure_point(comic: Comic, db: Session) -> str:
    """
    Analyze where the comic failed and determine recovery status
    
    Returns:
        Recovery status: PENDING, SCRIPT_READY, or PROCESSING
    """
    # Check if panels exist
    panel_count = db.query(ComicPanel).filter(
        ComicPanel.comic_id == comic.id
    ).count()
    
    # Check if images exist
    panels_with_images = db.query(ComicPanel).filter(
        ComicPanel.comic_id == comic.id,
        ComicPanel.image_url.isnot(None)
    ).count()
    
    # Decision tree
    if panel_count == 0:
        # No panels = script generation failed
        logger.info(f"Comic #{comic.id}: No panels found -> Reset to PENDING")
        return "PENDING"
    
    elif panels_with_images == 0:
        # Panels exist but no images = image generation failed
        logger.info(f"Comic #{comic.id}: {panel_count} panels, no images -> Reset to SCRIPT_READY")
        return "SCRIPT_READY"
    
    elif panels_with_images < panel_count:
        # Some images missing = partial image failure
        logger.info(f"Comic #{comic.id}: {panels_with_images}/{panel_count} panels have images -> Reset to SCRIPT_READY")
        return "SCRIPT_READY"
    
    elif comic.preview_video_url is None:
        # All images exist but no video
        
        # Case A: Stuck in RENDERING with all images (Comic #330 case)
        if comic.draft_job_status == 'RENDERING':
            logger.info(f"Comic #{comic.id}: Stuck in RENDERING but has all images -> Reset to PROCESSING")
            return "PROCESSING"
            
        # Case B: Video generation failed
        logger.info(f"Comic #{comic.id}: All images exist, no video -> Reset to PROCESSING")
        return "PROCESSING"
    
    else:
        # Everything exists but still FAILED? This shouldn't happen
        # Mark as COMPLETED
        logger.warning(f"Comic #{comic.id}: All assets exist but status is FAILED -> Mark as COMPLETED")
        return "COMPLETED"


def recover_failed_comic(comic: Comic, db: Session) -> Dict[str, Any]:
    """
    Recover a single failed comic
    
    Returns:
        Dict with recovery result
    """
    try:
        logger.info(f"=== RECOVERING COMIC #{comic.id} ===")
        logger.info(f"Current status: {comic.draft_job_status}")
        logger.info(f"Last error: {comic.last_error_message[:200] if comic.last_error_message else 'None'}")
        logger.info(f"Retry counts - Script: {comic.script_retry_count}, Image: {comic.image_retry_count}, Video: {comic.video_retry_count}")
        
        # Analyze failure point
        recovery_status = analyze_failure_point(comic, db)
        
        # Reset to recovery status
        comic.draft_job_status = recovery_status
        comic.locked_by = None
        comic.locked_at = None
        
        # Clear error message for fresh retry
        comic.last_error_message = f"[AUTO-RECOVERY] Previous error: {comic.last_error_message[:500] if comic.last_error_message else 'Unknown'}"
        comic.last_error_at = datetime.now()
        
        db.commit()
        
        logger.info(f"✅ Comic #{comic.id} recovered: {recovery_status}")
        
        return {
            "comic_id": comic.id,
            "status": "recovered",
            "recovery_status": recovery_status,
            "previous_error": comic.last_error_message[:200] if comic.last_error_message else None
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to recover comic #{comic.id}: {e}")
        db.rollback()
        return {
            "comic_id": comic.id,
            "status": "recovery_failed",
            "error": str(e)
        }


def process_failed_job_recovery(db: Session) -> Dict[str, Any]:
    """
    Main recovery processor - recovers all eligible failed comics
    
    Returns:
        Dict with recovery statistics
    """
    logger.info("========== STARTING FAILED JOB RECOVERY ==========")
    
    # Get failed comics
    failed_comics = get_failed_comics_for_recovery(db, limit=10)
    
    if not failed_comics:
        logger.info("No failed comics found for recovery")
        return {"processed": 0, "recovered": 0, "failed": 0}
    
    logger.info(f"Found {len(failed_comics)} failed comics for recovery")
    
    results = {
        "processed": 0,
        "recovered": 0,
        "failed": 0,
        "comics": []
    }
    
    for comic in failed_comics:
        result = recover_failed_comic(comic, db)
        results["processed"] += 1
        
        if result["status"] == "recovered":
            results["recovered"] += 1
        else:
            results["failed"] += 1
        
        results["comics"].append(result)
    
    logger.info("========== FAILED JOB RECOVERY COMPLETE ==========")
    logger.info(f"Results: {results['processed']} processed, {results['recovered']} recovered, {results['failed']} failed")
    
    return results
