"""
Fix Comic Completion Status
Checks if all panels have image URLs, and triggers video generation if needed.
Can be used to retry stuck jobs.
"""
import sys
import os
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_session_local
from app.models.comic import Comic
from app.models.comic_panel import ComicPanel
from app.services.video_queue import queue_video_generation
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_comic")

def fix_comic(comic_id: int):
    db = get_session_local()()
    try:
        comic = db.query(Comic).filter(Comic.id == comic_id).first()
        if not comic:
            logger.error(f"Comic {comic_id} not found")
            return
            
        logger.info(f"Checking comic {comic_id} status={comic.draft_job_status}")
        
        # Check panels
        panels = db.query(ComicPanel).filter(ComicPanel.comic_id == comic_id).all()
        total_panels = len(panels)
        panels_with_image = sum(1 for p in panels if p.image_url)
        
        logger.info(f"Panels: {panels_with_image}/{total_panels} have images")
        
        if panels_with_image >= total_panels and total_panels > 0:
            logger.info("All panels have images. Triggering video generation...")
            
            # Update timing if missing
            if not comic.render_completed_at:
                comic.render_completed_at = datetime.now()
            if not comic.clipping_completed_at:
                comic.clipping_completed_at = datetime.now()
            
            comic.draft_job_status = "PROCESSING"
            comic.video_started_at = datetime.now() 
            db.commit()
            
            # Prepare panel data
            video_payload_panels = [{
                "image_url": p.image_url,
                "narration": p.narration or p.page_narration or "",
                "dialogue": p.dialogues or [],
                "description": p.description or p.page_description or ""
            } for p in panels if p.image_url]
            
            # Queue to video worker
            result = queue_video_generation(comic_id, video_payload_panels)
            logger.info(f"Video queued: {result}")
            
        else:
            logger.warning("Not all panels have images. Cannot generate video.")
            # If URLs are missing but images exist in GCS, we might need to manually update them
            # This script assumes images are ALREADY in DB (which might be false for 151 if worker failed to save)
            
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_comic_completion.py <comic_id>")
        sys.exit(1)
        
    comic_id = int(sys.argv[1])
    fix_comic(comic_id)
