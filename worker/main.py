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
