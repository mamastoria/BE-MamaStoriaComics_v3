"""
Worker API
Handles Cloud Tasks for async processing
"""
from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.orm import Session
import logging
from typing import Dict, Any
import sys
from pathlib import Path
import time
import json

# Add root directory to python path to import core
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

try:
    import core
except ImportError:
    # Safe fallback
    import core

from app.core.database import get_db
from app.models.comic import Comic

router = APIRouter()
logger = logging.getLogger("nanobanana_worker")

@router.post("/generate-comic")
async def handle_generate_comic_task(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Worker handler for /tasks/generate-comic
    """
    job_id = payload.get("job_id")
    story = payload.get("story")
    style_id = payload.get("style_id")
    nuances = payload.get("nuances", [])
    
    logger.info(f"WORKER: Received task for job_id={job_id}")
    
    if not job_id:
        return {"status": "error", "message": "Missing job_id"}

    # 1. Update Status -> PROCESSING
    try:
        comic_id_int = int(job_id)
        comic = db.query(Comic).filter(Comic.id == comic_id_int).first()
    except ValueError:
        logger.error(f"Invalid job_id {job_id}")
        return {"status": "error", "message": "Invalid job_id"}

    if not comic:
        logger.error(f"Comic {job_id} not found in DB")
        # Proceed anyway? No, we need DB record to update status.
        return {"status": "error", "message": "Comic not found"}
        
    comic.draft_job_status = "PROCESSING"
    db.commit()
    
    try:
        # 2. Generate Script (Sync)
        logger.info(f"WORKER: Generating script for {job_id}...")
        script = core.make_two_part_script(story, style_id, nuances)
        
        # 3. Start Rendering
        logger.info(f"WORKER: Starting render for {job_id} (Background)...")
        # Run core logic in background thread but we wait for it
        core.start_render_all_job(script, job_id=job_id) 
        
        # WAIT LOOP for Cloud Run (keep request alive)
        # Timeout 15 mins (match task deadline)
        start_time = time.time()
        timeout = 900 
        
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError("Rendering timed out")
                
            job_state = core.get_job(job_id)
            if not job_state:
                time.sleep(1)
                continue

            status = job_state.get("status")
            
            if status == "done":
                logger.info(f"WORKER: Job {job_id} DONE.")
                break
            elif status == "error":
                err = job_state.get("error")
                raise RuntimeError(f"Render failed: {err}")
            
            time.sleep(3) # check every 3s
            
        # 4. Finalize DB
        logger.info(f"WORKER: Finalizing DB for {job_id}...")
        
        # Refresh session just in case
        db.expunge_all()
        comic = db.query(Comic).filter(Comic.id == comic_id_int).first()
        
        # Populate ComicPanel table
        from app.models.comic_panel import ComicPanel
        
        # Clear existing panels for this comic
        db.query(ComicPanel).filter(ComicPanel.comic_id == comic_id_int).delete()
        
        # Get job state
        job_state = core.get_job(job_id)
        if job_state:
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
                    panel = ComicPanel(
                        comic_id=comic_id_int,
                        page_number=part_no,
                        panel_number=i+1,
                        image_url=f"/api/preview/{job_id}/panel/{part_no}/{i}",
                        description=panel_data.get("description"),
                        narration=panel_data.get("narration"),
                        dialogues=panel_data.get("dialogues")
                    )
                    db.add(panel)
                    panel_counter += 1
            
            logger.info(f"WORKER: Added {panel_counter} panels to DB for {job_id}")
        
        comic.draft_job_status = "COMPLETED"
        comic.pdf_url = f"/api/pdf/{job_id}" 
        comic.preview_video_url = f"/viewer/{job_id}"
        
        # Try to generate PDF to ensure file exists
        try:
             core.ensure_job_pdf(job_id)
        except Exception as pdf_err:
             logger.warning(f"Draft PDF generation warning: {pdf_err}")

        db.commit()
        
    except Exception as e:
        logger.exception(f"Job {job_id} failed with error: {e}")
        
        db.expunge_all()
        comic = db.query(Comic).filter(Comic.id == comic_id_int).first()
        if comic:
            comic.draft_job_status = "FAILED"
            # Optional: save error message if column exists
        db.commit()
        # Re-raise to mark task as failed (Cloud Tasks will retry)
        # If we return 200, Task sees it as success. 
        # If error is deterministic, raising will cause infinite loop. 
        # Better return 200 but log error? Or 500?
        # Let's clean exit with 500 so logs show failure.
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"status": "ok", "job_id": job_id}
