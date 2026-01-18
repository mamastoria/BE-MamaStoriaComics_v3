"""
Worker Service Main Entry Point
Handles Cloud Tasks queue processing for render jobs
"""
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MamaStoria Worker",
    description="Background worker for comic rendering",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "ok": True,
        "service": "nanobanana-worker",
        "status": "healthy"
    }


@app.post("/tasks/render-part")
async def handle_render_task(request: Request):
    """
    Handle render task from Cloud Tasks queue
    
    Expected payload:
    {
        "comic_id": 123,
        "part_no": 1
    }
    """
    try:
        # Get task payload
        payload = await request.json()
        comic_id = payload.get("comic_id")
        part_no = payload.get("part_no")
        
        logger.info(f"Received render task: comic_id={comic_id}, part_no={part_no}")
        
        if not comic_id:
            raise HTTPException(status_code=400, detail="Missing comic_id")
        
        # Import here to avoid circular imports
        from app.core.database import get_session_local
        from app.services.job_processor import process_image_jobs
        
        # Process the render job
        SessionLocal = get_session_local()
        db = SessionLocal()
        try:
            result = process_image_jobs(db)
            logger.info(f"Render job completed: {result}")
            
            return {
                "ok": True,
                "message": "Render task completed",
                "result": result
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error processing render task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/video-generation")
async def handle_video_task(request: Request):
    """
    Handle video generation task from Cloud Tasks queue
    
    Expected payload:
    {
        "comic_id": 123
    }
    """
    try:
        payload = await request.json()
        comic_id = payload.get("comic_id")
        
        logger.info(f"Received video task: comic_id={comic_id}")
        
        if not comic_id:
            raise HTTPException(status_code=400, detail="Missing comic_id")
        
        from app.core.database import get_session_local
        from app.services.job_processor import process_video_jobs
        
        SessionLocal = get_session_local()
        db = SessionLocal()
        try:
            result = process_video_jobs(db)
            logger.info(f"Video job completed: {result}")
            
            return {
                "ok": True,
                "message": "Video task completed",
                "result": result
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error processing video task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
