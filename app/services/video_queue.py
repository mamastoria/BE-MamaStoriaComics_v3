"""
Video Queue Service
Handles queueing video generation jobs to Cloud Tasks
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Cloud Tasks settings
# Priority: GCP_PROJECT -> GOOGLE_CLOUD_PROJECT -> default
PROJECT_ID = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "nanobananacomic-482111"))
LOCATION = os.getenv("GCP_REGION", "us-central1")
QUEUE_NAME = "video-generation-queue"
VIDEO_WORKER_URL = os.getenv(
    "VIDEO_WORKER_URL", 
    "https://video-worker-us-1089713441636.us-central1.run.app/generate"
)
SERVICE_ACCOUNT_EMAIL = os.getenv(
    "CLOUD_TASKS_SA", 
    f"cloud-tasks-invoker@{PROJECT_ID}.iam.gserviceaccount.com"
)


def queue_video_generation(comic_id: int, panels_data: List[Dict[str, Any]], user_id: Optional[int] = None) -> Optional[str]:
    """
    Queue a video generation job to Cloud Tasks.
    
    Args:
        comic_id: ID of the comic to generate video for
        panels_data: List of panel data with image URLs and narration
        user_id: Optional user ID for tracking which user's video is being processed
    """
    try:
        from google.cloud import tasks_v2
        
        client = tasks_v2.CloudTasksClient()
        
        # Build the queue path
        parent = client.queue_path(PROJECT_ID, LOCATION, QUEUE_NAME)
        logger.info(f"Targeting Cloud Tasks Queue: {parent}")
        
        # Build the request payload with user_id
        payload = {
            "comic_id": comic_id,
            "user_id": user_id,
            "panels": panels_data
        }
        
        # Build the task
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": VIDEO_WORKER_URL,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps(payload).encode(),
                # OIDC token for authentication
                "oidc_token": {
                    "service_account_email": SERVICE_ACCOUNT_EMAIL,
                    "audience": VIDEO_WORKER_URL
                }
            }
        }
        
        # Create the task
        response = client.create_task(parent=parent, task=task)
        
        task_name = response.name
        logger.info(f"Created Cloud Task for comic {comic_id}: {task_name}")
        
        return task_name
        
    except ImportError:
        logger.error("google-cloud-tasks not installed. Install with: pip install google-cloud-tasks")
        return None
    except Exception as e:
        logger.exception(f"Failed to queue video generation for comic {comic_id}: {e}")
        return None


def get_task_status(task_name: str) -> Optional[Dict[str, Any]]:
    """
    Get the status of a Cloud Task.
    
    Args:
        task_name: Full task name from queue_video_generation
    
    Returns:
        Task info dict if found, None otherwise
    """
    try:
        from google.cloud import tasks_v2
        
        client = tasks_v2.CloudTasksClient()
        
        try:
            task = client.get_task(name=task_name)
            return {
                "name": task.name,
                "create_time": task.create_time.isoformat() if task.create_time else None,
                "schedule_time": task.schedule_time.isoformat() if task.schedule_time else None,
                "dispatch_count": task.dispatch_count,
                "response_count": task.response_count
            }
        except Exception as e:
            # Task might have been completed and deleted
            logger.info(f"Task not found (may be completed): {task_name}")
            return None
            
    except ImportError:
        logger.error("google-cloud-tasks not installed")
        return None
    except Exception as e:
        logger.exception(f"Failed to get task status: {e}")
        return None


# Fallback: Direct video generation (no queue)
def generate_video_directly(comic_id: int, panels_data: List[Dict[str, Any]]) -> Optional[str]:
    """
    Generate video directly without Cloud Tasks (fallback).
    This runs in the same process and may block.
    
    Use this only if Cloud Tasks is unavailable.
    """
    try:
        import sys
        from pathlib import Path
        
        ROOT_DIR = Path(__file__).resolve().parent.parent.parent
        if str(ROOT_DIR) not in sys.path:
            sys.path.append(str(ROOT_DIR))
        
        import video_generator
        
        logger.info(f"Generating video directly for comic {comic_id}...")
        
        video_url = video_generator.generate_video_for_comic(
            comic_id=comic_id,
            panels=panels_data,
            upload_to_gcs=True
        )
        
        return video_url
        
    except Exception as e:
        logger.exception(f"Direct video generation failed: {e}")
        return None
