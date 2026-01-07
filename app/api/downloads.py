"""
Downloads API endpoints
Handle file downloads from Google Cloud Storage
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from app.services.google_storage_service import GoogleStorageService
from app.core.database import get_db
from app.core.dependencies import get_optional_user
from app.models.user import User
from sqlalchemy.orm import Session
from typing import Optional
import logging
from urllib.parse import urlparse
import io
import subprocess
import tempfile
import os
from pathlib import Path

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/download/video")
async def download_video(
    url: str = Query(..., description="Full URL of the video file in Google Cloud Storage"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Download video file from Google Cloud Storage
    
    - **url**: Full URL of the video file
    
    If user has watermark=True setting (or is not logged in), a watermark is added.
    If user has watermark=False, no watermark is added.
    """
    try:
        # Determine if we should add watermark
        # Default to True if user is not logged in
        should_add_watermark = True
        if current_user:
            should_add_watermark = current_user.watermark
            
        # Parse URL to extract bucket and file path
        parsed_url = urlparse(url)
        
        # Validate that it's a Google Storage URL
        if "storage.googleapis.com" not in parsed_url.netloc:
            raise HTTPException(
                status_code=400,
                detail="Invalid URL. Must be a Google Cloud Storage URL (storage.googleapis.com)"
            )
        
        # Extract file path from URL
        # URL format: https://storage.googleapis.com/bucket-name/path/to/file.mp4
        path_parts = parsed_url.path.strip('/').split('/', 1)
        
        if len(path_parts) < 2:
            raise HTTPException(
                status_code=400,
                detail="Invalid URL format. Expected: https://storage.googleapis.com/bucket-name/path/to/file"
            )
        
        # bucket_name = path_parts[0]  # Not needed if using configured bucket
        file_path = path_parts[1]
        
        # Get filename from path
        filename = file_path.split('/')[-1]
        
        # Initialize Google Storage Service
        storage_service = GoogleStorageService()
        
        # Check if file exists
        if not storage_service.file_exists(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {file_path}"
            )
        
        # Get file metadata to determine content type
        try:
            metadata = storage_service.get_file_metadata(file_path)
            content_type = metadata.get('content_type', 'video/mp4')
        except Exception as e:
            logger.warning(f"Could not get metadata for {file_path}: {e}")
            content_type = 'video/mp4'
        
        # Download file from Google Storage
        logger.info(f"Downloading file: {file_path}")
        
        try:
            file_content = storage_service.download_file(file_path)
        except Exception as e:
            logger.error(f"Failed to download file from GCS: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download file from storage: {str(e)}"
            )
            
        # --- WATERMARK LOGIC ---
        if should_add_watermark:
            # Check for watermark image
            root_dir = Path(__file__).resolve().parent.parent.parent
            watermark_path = root_dir / "assets" / "img" / "mamastoria-large.png"
            
            if watermark_path.exists():
                try:
                    logger.info(f"Adding watermark from: {watermark_path}")
                    with tempfile.TemporaryDirectory() as temp_dir:
                        input_path = os.path.join(temp_dir, "input.mp4")
                        output_path = os.path.join(temp_dir, "output.mp4")
                        
                        # Write input file
                        with open(input_path, "wb") as f:
                            f.write(file_content)
                        
                        # FFmpeg command
                        # Overlay watermark at top-right with 20px padding (W-w-20:20)
                        # Use -y to overwrite output
                        # Use -preset fast for speed
                        cmd = [
                            "ffmpeg", "-y",
                            "-i", input_path,
                            "-i", str(watermark_path),
                            "-filter_complex", "[1]scale=50:-1[wm];[0][wm]overlay=W-w-20:H-h-20",
                            "-c:a", "copy",
                            "-preset", "fast", 
                            output_path
                        ]
                        
                        # Run ffmpeg
                        process = subprocess.run(
                            cmd, 
                            capture_output=True, 
                            timeout=180  # 3 minutes max
                        )
                        
                        if process.returncode == 0 and os.path.exists(output_path):
                            # Read processed file
                            with open(output_path, "rb") as f:
                                file_content = f.read()
                            logger.info("Watermark added successfully to downloaded video")
                        else:
                            logger.warning(f"FFmpeg failed to add watermark: {process.stderr.decode() if process.stderr else 'Unknown error'}")
                except Exception as e:
                    logger.error(f"Error adding watermark: {e}")
                    # Continue with original file_content
            else:
                logger.warning(f"Watermark file not found at {watermark_path}")
        else:
            logger.info("Skipping watermark (user preference)")
        
        # Create a generator to stream the file content in chunks
        def iterfile():
            chunk_size = 8192 * 1024  # 8MB chunks
            offset = 0
            while offset < len(file_content):
                yield file_content[offset:offset + chunk_size]
                offset += chunk_size
        
        # Prepare headers for download
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': content_type,
            'Content-Length': str(len(file_content)),
            'Access-Control-Expose-Headers': 'Content-Disposition, Content-Length',
            'Accept-Ranges': 'bytes',
        }
        
        # Return streaming response
        return StreamingResponse(
            iterfile(),
            media_type=content_type,
            headers=headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download video: {str(e)}"
        )


@router.get("/download/file")
async def download_file(
    url: str = Query(..., description="Full URL of the file in Google Cloud Storage")
):
    """
    Download any file from Google Cloud Storage
    
    - **url**: Full URL of the file (e.g., https://storage.googleapis.com/bucket-name/path/to/file.pdf)
    
    Returns file as streaming response with proper headers for direct download in Flutter
    """
    try:
        # Parse URL to extract bucket and file path
        parsed_url = urlparse(url)
        
        # Validate that it's a Google Storage URL
        if "storage.googleapis.com" not in parsed_url.netloc:
            raise HTTPException(
                status_code=400,
                detail="Invalid URL. Must be a Google Cloud Storage URL (storage.googleapis.com)"
            )
        
        # Extract file path from URL
        # URL format: https://storage.googleapis.com/bucket-name/path/to/file.mp4
        path_parts = parsed_url.path.strip('/').split('/', 1)
        
        if len(path_parts) < 2:
            raise HTTPException(
                status_code=400,
                detail="Invalid URL format. Expected: https://storage.googleapis.com/bucket-name/path/to/file"
            )
        
        file_path = path_parts[1]
        
        # Get filename from path
        filename = file_path.split('/')[-1]
        
        # Initialize Google Storage Service
        storage_service = GoogleStorageService()
        
        # Check if file exists
        if not storage_service.file_exists(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {file_path}"
            )
        
        # Get file metadata to determine content type
        try:
            metadata = storage_service.get_file_metadata(file_path)
            content_type = metadata.get('content_type', 'application/octet-stream')
            file_size = metadata.get('size', 0)
        except Exception as e:
            logger.warning(f"Could not get metadata for {file_path}: {e}")
            content_type = 'application/octet-stream'
            file_size = None
        
        # Download file from Google Storage
        logger.info(f"Downloading file: {file_path}")
        
        # Download file content
        try:
            file_content = storage_service.download_file(file_path)
        except Exception as e:
            logger.error(f"Failed to download file from GCS: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download file from storage: {str(e)}"
            )
        
        # Create a generator to stream the file content in chunks
        def iterfile():
            chunk_size = 8192 * 1024  # 8MB chunks
            offset = 0
            while offset < len(file_content):
                yield file_content[offset:offset + chunk_size]
                offset += chunk_size
        
        # Prepare headers for download
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': content_type,
            'Content-Length': str(len(file_content)),
            'Access-Control-Expose-Headers': 'Content-Disposition, Content-Length',
            'Accept-Ranges': 'bytes',
        }
        
        # Return streaming response
        return StreamingResponse(
            iterfile(),
            media_type=content_type,
            headers=headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {str(e)}"
        )
