"""
Render Queue Service
Queues comic part rendering jobs to Cloud Tasks
Each part (1 of 2) is queued as a separate job for isolated processing
"""
import os
import json
import logging
from typing import Dict, Any, Optional, List
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
import datetime

logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "nanobananacomic-482111")
LOCATION = os.environ.get("CLOUD_TASKS_LOCATION", "asia-southeast2")
RENDER_QUEUE_NAME = os.environ.get("RENDER_QUEUE_NAME", "render-queue")

# Worker URL - the nanobanana-worker Cloud Run service
RENDER_WORKER_URL = os.environ.get(
    "RENDER_WORKER_URL",
    "https://nanobanana-worker-1089713441636.asia-southeast2.run.app"
)

# Service account for Cloud Tasks to call Cloud Run
SERVICE_ACCOUNT_EMAIL = os.environ.get(
    "CLOUD_TASKS_SERVICE_ACCOUNT",
    "cloud-tasks-invoker@nanobananacomic-482111.iam.gserviceaccount.com"
)


def get_tasks_client():
    """Get Cloud Tasks client with caching"""
    if not hasattr(get_tasks_client, "_client"):
        get_tasks_client._client = tasks_v2.CloudTasksClient()
    return get_tasks_client._client


def queue_render_part(
    comic_id: int,
    part_no: int,
    script_data: Dict[str, Any],
    style: Optional[str] = None,
    delay_seconds: int = 0
) -> Optional[str]:
    """
    Queue a single part render job to Cloud Tasks.
    
    Args:
        comic_id: Comic ID in database
        part_no: Part number (1 or 2)
        script_data: Full script data for the comic
        style: Style ID
        delay_seconds: Delay before task execution
        
    Returns:
        Task name if successful, None if failed
    """
    try:
        client = get_tasks_client()
        
        parent = client.queue_path(PROJECT_ID, LOCATION, RENDER_QUEUE_NAME)
        
        # Build payload
        payload = {
            "comic_id": comic_id,
            "part_no": part_no,
            "script": script_data,
            "style": style
        }
        
        # Target URL for render-part endpoint
        target_url = f"{RENDER_WORKER_URL}/tasks/render-part"
        
        # Build task
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": target_url,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps(payload).encode(),
                "oidc_token": {
                    "service_account_email": SERVICE_ACCOUNT_EMAIL,
                    "audience": RENDER_WORKER_URL
                }
            }
        }
        
        # Add delay if specified
        if delay_seconds > 0:
            schedule_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=delay_seconds)
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(schedule_time)
            task["schedule_time"] = timestamp
        
        # Create task
        response = client.create_task(parent=parent, task=task)
        logger.info(f"Queued render job: comic={comic_id}, part={part_no}, task={response.name}")
        
        return response.name
        
    except Exception as e:
        logger.error(f"Failed to queue render part: {e}")
        return None


def queue_both_parts(
    comic_id: int,
    script_data: Dict[str, Any],
    style: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """
    Queue both parts of a comic for rendering.
    
    Returns:
        Dict with part1 and part2 task names (or None if failed)
    """
    results = {}
    
    # Queue Part 1
    results["part1"] = queue_render_part(
        comic_id=comic_id,
        part_no=1,
        script_data=script_data,
        style=style,
        delay_seconds=0  # Start immediately
    )
    
    # Queue Part 2 (can run in parallel with Part 1)
    results["part2"] = queue_render_part(
        comic_id=comic_id,
        part_no=2,
        script_data=script_data,
        style=style,
        delay_seconds=0  # Start immediately
    )
    
    return results


def queue_crop_part(
    comic_id: int,
    part_no: int,
    grid_gcs_url: str
) -> Optional[str]:
    """
    Queue a cropping job for a single part.
    
    Args:
        comic_id: Comic ID
        part_no: Part number (1 or 2)
        grid_gcs_url: GCS URL of the full grid image
        
    Returns:
        Task name if successful
    """
    try:
        client = get_tasks_client()
        
        parent = client.queue_path(PROJECT_ID, LOCATION, RENDER_QUEUE_NAME)
        
        payload = {
            "comic_id": comic_id,
            "part_no": part_no,
            "grid_gcs_url": grid_gcs_url
        }
        
        target_url = f"{RENDER_WORKER_URL}/tasks/crop-part"
        
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": target_url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode(),
                "oidc_token": {
                    "service_account_email": SERVICE_ACCOUNT_EMAIL,
                    "audience": RENDER_WORKER_URL
                }
            }
        }
        
        response = client.create_task(parent=parent, task=task)
        logger.info(f"Queued crop job: comic={comic_id}, part={part_no}, task={response.name}")
        
        return response.name
        
    except Exception as e:
        logger.error(f"Failed to queue crop part: {e}")
        return None
