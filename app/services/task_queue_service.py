"""
Cloud Tasks Service
Handles sending tasks to the worker queue
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import timedelta

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2, duration_pb2

logger = logging.getLogger("nanobanana_tasks")

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "nanobananacomic-482111")
LOCATION = os.getenv("CLOUD_TASKS_LOCATION", "asia-southeast2")
QUEUE_NAME = os.getenv("CLOUD_TASKS_QUEUE", "comic-generation-queue")
WORKER_URL = os.getenv("WORKER_SERVICE_URL", "https://nanobanana-backend-1089713441636.asia-southeast2.run.app")


class TaskQueueService:
    """Service for managing Cloud Tasks"""
    
    def __init__(self):
        self.client = tasks_v2.CloudTasksClient()
        self.queue_path = self.client.queue_path(PROJECT_ID, LOCATION, QUEUE_NAME)
    
    def create_task(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
        delay_seconds: int = 0,
        deadline_seconds: int = 900  # 15 minutes default
    ) -> str:
        """
        Create a Cloud Task
        
        Args:
            endpoint: Worker endpoint path (e.g., "/tasks/generate-comic")
            payload: JSON payload to send
            task_id: Optional unique task ID (for deduplication)
            delay_seconds: Delay before task execution
            deadline_seconds: Max time for task to complete
            
        Returns:
            Task name
        """
        url = f"{WORKER_URL}{endpoint}"
        
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode(),
                "oidc_token": {
                    "service_account_email": f"nanobanana-comic-sa@{PROJECT_ID}.iam.gserviceaccount.com"
                }
            },
            "dispatch_deadline": duration_pb2.Duration(seconds=deadline_seconds)
        }
        
        # Set task name for deduplication
        if task_id:
            task["name"] = f"{self.queue_path}/tasks/{task_id}"
        
        # Set schedule time for delayed tasks
        if delay_seconds > 0:
            from datetime import datetime, timezone
            schedule_time = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(schedule_time)
            task["schedule_time"] = timestamp
        
        try:
            response = self.client.create_task(
                request={"parent": self.queue_path, "task": task}
            )
            logger.info(f"Created task: {response.name}")
            return response.name
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            raise
    
    def send_generate_comic_task(
        self,
        job_id: str,
        story: str,
        style_id: Optional[str] = None,
        nuances: list = [],
        pages: int = 2
    ) -> str:
        """
        Send a comic generation task to the queue
        
        Args:
            job_id: Unique job identifier
            story: Story text
            style_id: Comic style ID
            nuances: List of nuance IDs
            pages: Number of pages
            
        Returns:
            Task name
        """
        payload = {
            "job_id": job_id,
            "story": story,
            "style_id": style_id,
            "nuances": nuances,
            "pages": pages
        }
        
        return self.create_task(
            endpoint="/tasks/generate-comic",
            payload=payload,
            task_id=f"generate-{job_id}",
            deadline_seconds=900  # 15 minutes for full comic
        )
    
    def send_generate_panel_task(
        self,
        job_id: str,
        panel_index: int,
        panel_data: Dict[str, Any],
        style_id: str
    ) -> str:
        """
        Send a single panel generation task
        """
        payload = {
            "job_id": job_id,
            "panel_index": panel_index,
            "panel_data": panel_data,
            "style_id": style_id
        }
        
        return self.create_task(
            endpoint="/tasks/generate-panel",
            payload=payload,
            task_id=f"panel-{job_id}-{panel_index}",
            deadline_seconds=300  # 5 minutes per panel
        )
    
    def send_generate_pdf_task(self, job_id: str) -> str:
        """
        Send a PDF generation task
        """
        payload = {"job_id": job_id}
        
        return self.create_task(
            endpoint="/tasks/generate-pdf",
            payload=payload,
            task_id=f"pdf-{job_id}",
            deadline_seconds=180  # 3 minutes for PDF
        )


# Singleton instance
_task_service: Optional[TaskQueueService] = None


def get_task_service() -> TaskQueueService:
    """Get or create TaskQueueService singleton"""
    global _task_service
    if _task_service is None:
        _task_service = TaskQueueService()
    return _task_service
