"""
Video Worker Service
Dedicated Cloud Run service for video generation
Memory: 8GB | CPU: 4 | Concurrency: 1
"""

import os
import sys
import json
import logging
import tempfile
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("video-worker")

# Add parent directory to path for imports
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import video generator from parent project
try:
    import video_generator
    logger.info("Video generator module loaded successfully")
except ImportError as e:
    logger.error(f"Failed to import video_generator: {e}")
    video_generator = None

# Import database utilities
try:
    from app.core.database import get_session_local
    from app.models.comic import Comic
    from app.models.notification import Notification
    logger.info("Database modules loaded successfully")
except ImportError as e:
    logger.error(f"Failed to import database modules: {e}")
    get_session_local = None
    Comic = None

# Initialize FastAPI
app = FastAPI(
    title="Video Worker Service",
    description="Dedicated service for video generation",
    version="1.0.0"
)


# Request/Response models
class PanelData(BaseModel):
    image_url: str
    narration: Optional[str] = ""
    dialogue: Optional[List[Dict[str, str]]] = []
    description: Optional[str] = ""


class VideoGenerationRequest(BaseModel):
    comic_id: int
    user_id: Optional[int] = None
    panels: List[Dict[str, Any]]


class VideoGenerationResponse(BaseModel):
    ok: bool
    message: str
    comic_id: int
    user_id: Optional[int] = None
    video_url: Optional[str] = None
    error: Optional[str] = None


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    return {
        "status": "healthy",
        "service": "video-worker",
        "ffmpeg_available": video_generator is not None and video_generator.check_ffmpeg() if video_generator else False
    }


# Main video generation endpoint
@app.post("/generate", response_model=VideoGenerationResponse)
async def generate_video(request: VideoGenerationRequest):
    """
    Generate video for a comic.
    
    This endpoint is called by Cloud Tasks with comic_id and panel data.
    It processes the video synchronously (Cloud Tasks handles timeout/retry).
    """
    comic_id = request.comic_id
    panels_data = request.panels
    
    logger.info(f"=== VIDEO GENERATION STARTED ===")
    logger.info(f"Comic ID: {comic_id}")
    logger.info(f"Panels count: {len(panels_data)}")
    
    if not video_generator:
        logger.error("Video generator module not available")
        raise HTTPException(
            status_code=500,
            detail="Video generator module not available"
        )
    
    if not get_session_local:
        logger.error("Database module not available")
        raise HTTPException(
            status_code=500,
            detail="Database module not available"
        )
    
    try:
        # Generate video using the existing video_generator module
        logger.info(f"Calling video_generator.generate_video_for_comic...")
        
        video_url = video_generator.generate_video_for_comic(
            comic_id=comic_id,
            panels=panels_data,
            upload_to_gcs=True
        )
        
        if video_url:
            logger.info(f"Video generated successfully: {video_url}")
            
            # Update database
            try:
                from datetime import datetime
                SessionLocal = get_session_local()
                db = SessionLocal()
                
                comic = db.query(Comic).filter(Comic.id == comic_id).first()
                if comic:
                    comic.preview_video_url = video_url
                    comic.draft_job_status = 'COMPLETED'  # Critical: mark as done
                    comic.locked_by = None  # Critical: clear lock
                    comic.locked_at = None
                    comic.video_completed_at = datetime.now()
                    
                    # Create notification
                    new_notif = Notification(
                        user_id=comic.user_id,
                        type="create",
                        title="Komik Selesai",
                        message=f"Komik '{comic.title}' sudah selesai, yuk lihat komik buatanmu!",
                        img_url=comic.cover_url
                    )
                    db.add(new_notif)
                    
                    db.commit()
                    logger.info(f"Database updated for comic {comic_id}: status=COMPLETED, lock cleared, notification created")
                else:
                    logger.warning(f"Comic {comic_id} not found in database")
                    
                db.close()
            except Exception as db_error:
                logger.error(f"Database update failed: {db_error}")
            
            return VideoGenerationResponse(
                ok=True,
                message="Video generated successfully",
                comic_id=comic_id,
                user_id=request.user_id,
                video_url=video_url
            )
        else:
            logger.error(f"Video generation returned None for comic {comic_id}")
            
            # Update status to FAILED - but keep PROCESSING so it can retry
            try:
                from datetime import datetime
                SessionLocal = get_session_local()
                db = SessionLocal()
                comic = db.query(Comic).filter(Comic.id == comic_id).first()
                if comic:
                    # Clear lock so it can be retried
                    comic.locked_by = None
                    comic.locked_at = None
                    comic.video_retry_count = (comic.video_retry_count or 0) + 1
                    comic.last_error_message = "Video generator returned None"
                    comic.last_error_at = datetime.now()
                    db.commit()
                    logger.info(f"Comic {comic_id} marked for retry (attempt {comic.video_retry_count})")
                db.close()
            except Exception:
                pass
            
            return VideoGenerationResponse(
                ok=False,
                message="Video generation failed",
                comic_id=comic_id,
                user_id=request.user_id,
                error="Video generator returned None"
            )
            
    except Exception as e:
        logger.exception(f"Video generation failed for comic {comic_id}: {e}")
        
        # Update status to allow retry
        try:
            from datetime import datetime
            SessionLocal = get_session_local()
            db = SessionLocal()
            comic = db.query(Comic).filter(Comic.id == comic_id).first()
            if comic:
                # Clear lock so it can be retried
                comic.locked_by = None
                comic.locked_at = None
                comic.video_retry_count = (comic.video_retry_count or 0) + 1
                comic.last_error_message = str(e)[:1000]
                comic.last_error_at = datetime.now()
                db.commit()
                logger.info(f"Comic {comic_id} marked for retry after error (attempt {comic.video_retry_count})")
            db.close()
        except Exception:
            pass
        
        return VideoGenerationResponse(
            ok=False,
            message="Video generation failed",
            comic_id=comic_id,
            user_id=None,
            error=str(e)
        )


# Cloud Tasks callback endpoint (same as /generate but more explicit)
@app.post("/tasks/generate-video")
async def cloud_tasks_generate_video(request: Request):
    """
    Endpoint for Cloud Tasks invocation.
    Parses the raw request body from Cloud Tasks.
    """
    try:
        body = await request.json()
        comic_id = body.get("comic_id")
        panels = body.get("panels", [])
        
        if not comic_id:
            raise HTTPException(status_code=400, detail="comic_id is required")
        
        # Create request object and call main endpoint
        gen_request = VideoGenerationRequest(comic_id=comic_id, panels=panels)
        return await generate_video(gen_request)
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")


# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "message": "Internal server error",
            "error": str(exc)
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
