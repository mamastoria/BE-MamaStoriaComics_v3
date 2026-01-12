"""
NanoBanana Comic Worker Service
Handles heavy AI generation tasks asynchronously
"""
from __future__ import annotations

import os
import json
import logging
import traceback
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import core module for AI generation
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nanobanana_worker")

# ============================================================
# APP
# ============================================================
app = FastAPI(
    title="NanoBanana Comic Worker",
    description="Background worker for AI comic generation"
)


# ============================================================
# REQUEST MODELS
# ============================================================
class GenerateTaskPayload(BaseModel):
    """Payload received from Cloud Tasks"""
    job_id: str
    story: str
    style_id: Optional[str] = None
    nuances: list = []
    pages: int = 2
    callback_url: Optional[str] = None  # URL to notify when done


class GeneratePanelPayload(BaseModel):
    """Payload for generating a single panel"""
    job_id: str
    panel_index: int
    panel_data: Dict[str, Any]
    style_id: str


# ============================================================
# HEALTH CHECK
# ============================================================
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "worker",
        "project_id": core.PROJECT_ID
    }


# ============================================================
# TASK HANDLERS
# ============================================================
@app.post("/tasks/generate-comic")
async def handle_generate_comic(request: Request):
    """
    Handle comic generation task from Cloud Tasks
    
    This endpoint is called by Cloud Tasks queue.
    It processes the entire comic generation workflow.
    """
    try:
        # Parse request body
        body = await request.json()
        payload = GenerateTaskPayload(**body)
        
        logger.info(f"[Worker] Starting job: {payload.job_id}")
        
        # Update job status to processing
        core.update_job_status(payload.job_id, "processing", progress=0)
        
        # Step 1: Generate script
        logger.info(f"[Worker] Generating script for job: {payload.job_id}")
        core.update_job_status(payload.job_id, "processing", progress=10, stage="generating_script")
        
        script_result = core.call_script_generation(
            story=payload.story,
            style_id=payload.style_id,
            nuances=payload.nuances,
            pages=payload.pages
        )
        
        if not script_result.get("ok"):
            raise Exception(f"Script generation failed: {script_result.get('error')}")
        
        script = script_result.get("script", [])
        core.save_job_script(payload.job_id, script)
        
        # Step 2: Generate panels
        total_panels = len(script)
        for idx, panel in enumerate(script):
            progress = 20 + int((idx / total_panels) * 70)  # 20% - 90%
            
            logger.info(f"[Worker] Generating panel {idx + 1}/{total_panels} for job: {payload.job_id}")
            core.update_job_status(
                payload.job_id, 
                "processing", 
                progress=progress, 
                stage=f"generating_panel_{idx + 1}"
            )
            
            # Generate image for this panel
            image_result = core.generate_panel_image(
                job_id=payload.job_id,
                panel_index=idx,
                panel_data=panel,
                style_id=payload.style_id
            )
            
            if not image_result.get("ok"):
                logger.warning(f"[Worker] Panel {idx + 1} failed, retrying...")
                # Retry once
                image_result = core.generate_panel_image(
                    job_id=payload.job_id,
                    panel_index=idx,
                    panel_data=panel,
                    style_id=payload.style_id
                )
        
        # Step 3: Finalize
        logger.info(f"[Worker] Finalizing job: {payload.job_id}")
        core.update_job_status(payload.job_id, "processing", progress=95, stage="finalizing")
        
        # Generate PDF if needed
        core.generate_job_pdf(payload.job_id)
        
        # Mark complete
        core.update_job_status(payload.job_id, "completed", progress=100)
        
        logger.info(f"[Worker] Job completed: {payload.job_id}")
        
        return {"ok": True, "job_id": payload.job_id, "status": "completed"}
        
    except Exception as e:
        logger.error(f"[Worker] Job failed: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Update job status to failed
        if 'payload' in locals():
            core.update_job_status(
                payload.job_id, 
                "failed", 
                error=str(e)
            )
        
        # Return 200 to prevent Cloud Tasks from retrying indefinitely
        # The job status is already marked as failed in the database
        return {"ok": False, "error": str(e)}


@app.post("/tasks/generate-panel")
async def handle_generate_panel(request: Request):
    """
    Handle single panel generation task
    
    For more granular control, each panel can be a separate task
    """
    try:
        body = await request.json()
        payload = GeneratePanelPayload(**body)
        
        logger.info(f"[Worker] Generating panel {payload.panel_index} for job: {payload.job_id}")
        
        result = core.generate_panel_image(
            job_id=payload.job_id,
            panel_index=payload.panel_index,
            panel_data=payload.panel_data,
            style_id=payload.style_id
        )
        
        return {"ok": True, "panel_index": payload.panel_index, "result": result}
        
    except Exception as e:
        logger.error(f"[Worker] Panel generation failed: {str(e)}")
        return {"ok": False, "error": str(e)}


class RenderPartPayload(BaseModel):
    """Payload for rendering a single comic part (1 job = 1 part)"""
    comic_id: int
    part_no: int  # 1 or 2
    script: Dict[str, Any]
    style: Optional[str] = None


@app.post("/tasks/render-part")
async def handle_render_part(request: Request):
    """
    Handle single part rendering task (1 part = 1 job)
    
    This endpoint is called by Cloud Tasks queue.
    Each part (9 panels as 3x3 grid) is processed as a separate job.
    This prevents OOM by isolating each render job.
    """
    import time
    from datetime import datetime
    # Import necessary DB and services modules
    from app.core.database import get_session_local
    from app.models.comic import Comic
    from app.models.comic_panel import ComicPanel
    from app.services.video_queue import queue_video_generation
    
    try:
        body = await request.json()
        payload = RenderPartPayload(**body)
        
        comic_id = payload.comic_id
        part_no = payload.part_no
        script = payload.script
        
        logger.info(f"[Worker] Starting PART {part_no} render for comic {comic_id}")
        
        start_time = time.time()
        
        # Render single part using core function
        part_result = core.render_part_payload(
            script=script,
            part_no=part_no,
            job_id=str(comic_id),
            style=payload.style
        )
        
        elapsed = time.time() - start_time
        logger.info(f"[Worker] PART {part_no} for comic {comic_id} completed in {elapsed:.1f}s")
        
        # ---------------------------------------------------------
        # SAVE RESULTS TO DATABASE & CHECK COMPLETION
        # ---------------------------------------------------------
        db = get_session_local()()
        try:
            # 1. Update Comic Status
            comic = db.query(Comic).filter(Comic.id == comic_id).first()
            if not comic:
                logger.error(f"[Worker] Comic {comic_id} not found in DB")
                return {"ok": False, "error": "Comic not found"}

            # Set render_started_at if this is the first part to complete
            if not comic.render_started_at:
                comic.render_started_at = datetime.now()
            
            # Set clipping_started_at on first part
            if part_no == 1 and not comic.clipping_started_at:
                comic.clipping_started_at = datetime.now()
            
            # 2. Save Panel URLs
            panel_urls = part_result.get("panel_urls", [])
            saved_count = 0
            for i, url in enumerate(panel_urls):
                if url:
                    panel_idx = i + 1
                    panel = db.query(ComicPanel).filter(
                        ComicPanel.comic_id == comic_id,
                        ComicPanel.page_number == part_no,
                        ComicPanel.panel_number == panel_idx
                    ).first()
                    
                    if panel:
                        panel.image_url = url
                        saved_count += 1
            
            logger.info(f"[Worker] Saved {saved_count} panel URLs for comic {comic_id} part {part_no}")
            
            # Save Grid URL (optional, maybe as cover if Part 1 Panel 1?)
            if part_no == 1 and panel_urls and panel_urls[0]:
                comic.cover_url = panel_urls[0]
                
            db.commit()
            
            # Small delay to handle race condition between parallel parts
            import time as time_module
            time_module.sleep(2)  # Wait 2 seconds for other part to commit
            
            # Refresh session to get latest data
            db.expire_all()
            
            # 3. Check if ALL parts are completed
            # We check if all panels for both parts have image_url
            panels_ready = db.query(ComicPanel).filter(
                ComicPanel.comic_id == comic_id,
                ComicPanel.image_url.isnot(None)
            ).count()
            
            total_panels_db = db.query(ComicPanel).filter(
                ComicPanel.comic_id == comic_id
            ).count()
            
            logger.info(f"[Worker] Check Completion: {panels_ready}/{total_panels_db} panels ready")
            
            if panels_ready >= total_panels_db and total_panels_db > 0:
                # ALL PARTS COMPLETED!
                logger.info(f"[Worker] All parts completed for comic {comic_id}. Triggering Video Generation...")
                
                # Update status
                comic.render_completed_at = datetime.now()
                comic.clipping_completed_at = datetime.now()
                comic.video_started_at = datetime.now()
                comic.draft_job_status = "PROCESSING" # Still processing video
                db.commit()
                
                # Fetch all panels to prepare payload for video worker
                all_panels = db.query(ComicPanel).filter(
                    ComicPanel.comic_id == comic_id,
                    ComicPanel.image_url.isnot(None)
                ).order_by(ComicPanel.page_number, ComicPanel.panel_number).all()
                
                video_payload_panels = [{
                    "image_url": p.image_url,
                    "narration": p.narration or p.page_narration or "",
                    "dialogue": p.dialogues or [],
                    "description": p.description or p.page_description or ""
                } for p in all_panels]
                
                # Trigger Video Worker via Queue
                queue_video_generation(comic_id, video_payload_panels)
                
            else:
                logger.info(f"[Worker] Comic {comic_id} partly done. Waiting for other parts.")
                
        finally:
            db.close()
            
        # ---------------------------------------------------------
        
        # Return result (panel URLs, grid URL, etc)
        return {
            "ok": True,
            "comic_id": comic_id,
            "part_no": part_no,
            "panel_urls": part_result.get("panel_urls", []),
            "grid_gcs_url": part_result.get("grid_gcs_url"),
            "render_time_seconds": round(elapsed, 1)
        }
        
    except Exception as e:
        logger.error(f"[Worker] Part render failed: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return 200 with error to prevent infinite retry
        return {
            "ok": False, 
            "error": str(e),
            "comic_id": payload.comic_id if 'payload' in locals() else None,
            "part_no": payload.part_no if 'payload' in locals() else None
        }


class CropPartPayload(BaseModel):
    """Payload for cropping a single comic part grid"""
    comic_id: int
    part_no: int
    grid_gcs_url: str


@app.post("/tasks/crop-part")
async def handle_crop_part(request: Request):
    """
    Handle single part cropping task (1 crop = 1 job)
    
    Calls the smart-crop-worker Cloud Function to crop 3x3 grid into 9 panels.
    """
    import time
    
    try:
        body = await request.json()
        payload = CropPartPayload(**body)
        
        comic_id = payload.comic_id
        part_no = payload.part_no
        grid_gcs_url = payload.grid_gcs_url
        
        logger.info(f"[Worker] Starting CROP for PART {part_no} of comic {comic_id}")
        
        start_time = time.time()
        
        # Call smart crop service
        panel_urls = core.call_smart_crop_service(
            grid_gcs_url=grid_gcs_url,
            job_id=str(comic_id),
            part_no=part_no
        )
        
        elapsed = time.time() - start_time
        logger.info(f"[Worker] CROP PART {part_no} for comic {comic_id} completed in {elapsed:.1f}s, {len(panel_urls)} panels")
        
        return {
            "ok": True,
            "comic_id": comic_id,
            "part_no": part_no,
            "panel_urls": panel_urls,
            "crop_time_seconds": round(elapsed, 1)
        }
        
    except Exception as e:
        logger.error(f"[Worker] Crop failed: {str(e)}")
        logger.error(traceback.format_exc())
        
        return {
            "ok": False,
            "error": str(e),
            "comic_id": payload.comic_id if 'payload' in locals() else None,
            "part_no": payload.part_no if 'payload' in locals() else None
        }


@app.post("/tasks/generate-pdf")
async def handle_generate_pdf(request: Request):
    """
    Handle PDF generation task
    """
    try:
        body = await request.json()
        job_id = body.get("job_id")
        
        logger.info(f"[Worker] Generating PDF for job: {job_id}")
        
        result = core.generate_job_pdf(job_id)
        
        return {"ok": True, "job_id": job_id, "pdf_url": result.get("pdf_url")}
        
    except Exception as e:
        logger.error(f"[Worker] PDF generation failed: {str(e)}")
        return {"ok": False, "error": str(e)}


# ============================================================
# ERROR HANDLERS
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"ok": False, "error": str(exc)}
    )


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
