"""
Downloads API endpoints
Handle file downloads from Google Cloud Storage
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.services.google_storage_service import GoogleStorageService
import logging
from urllib.parse import urlparse
import io

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/download/video")
async def download_video(
    url: str = Query(..., description="Full URL of the video file in Google Cloud Storage")
):
    """
    Download video file from Google Cloud Storage
    
    - **url**: Full URL of the video file (e.g., https://storage.googleapis.com/bucket-name/path/to/video.mp4)
    
    Returns video file as streaming response with proper headers for direct download in Flutter
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
            file_size = metadata.get('size', 0)
        except Exception as e:
            logger.warning(f"Could not get metadata for {file_path}: {e}")
            content_type = 'video/mp4'
            file_size = None
        
        # Download file from Google Storage
        logger.info(f"Downloading file: {file_path}")
        file_content = storage_service.download_file(file_path)
        
        # Create a BytesIO object for streaming
        file_stream = io.BytesIO(file_content)
        
        # Prepare headers for download
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': content_type,
            'Access-Control-Expose-Headers': 'Content-Disposition, Content-Length',
        }
        
        if file_size:
            headers['Content-Length'] = str(file_size)
        
        # Return streaming response
        return StreamingResponse(
            file_stream,
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
        file_content = storage_service.download_file(file_path)
        
        # Create a BytesIO object for streaming
        file_stream = io.BytesIO(file_content)
        
        # Prepare headers for download
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': content_type,
            'Access-Control-Expose-Headers': 'Content-Disposition, Content-Length',
        }
        
        if file_size:
            headers['Content-Length'] = str(file_size)
        
        # Return streaming response
        return StreamingResponse(
            file_stream,
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
