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
