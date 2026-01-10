"""
Admin API endpoints for Cloud Logging integration and performance monitoring.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime, timedelta
import logging
import re

logger = logging.getLogger("admin_api")

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


# Try to import Google Cloud Logging
try:
    from google.cloud import logging as cloud_logging
    from google.cloud.logging_v2 import DESCENDING
    CLOUD_LOGGING_AVAILABLE = True
except ImportError:
    CLOUD_LOGGING_AVAILABLE = False
    logger.warning("google-cloud-logging not installed, using mock data")


def parse_log_for_performance(entries: list) -> dict:
    """
    Analyze log entries to extract performance metrics.
    
    Looks for patterns like:
    - "JOB {job_id}: Starting PARALLEL rendering"
    - "JOB {job_id}: Parallel render DONE in {X}s"
    - "Smart Crop Success: Job {job_id}"
    - "Video generated successfully"
    """
    
    jobs = {}  # job_id -> {start_time, end_time, steps}
    
    for entry in entries:
        timestamp = entry.get("timestamp")
        message = entry.get("message", "")
        
        # Extract job/comic ID from various log patterns
        job_match = re.search(r'(?:JOB|Job|comic[_\s]?(?:id)?[:\s]*)(\d+)', message, re.IGNORECASE)
        comic_match = re.search(r'comic[_\s]?(\d+)', message, re.IGNORECASE)
        
        job_id = None
        if job_match:
            job_id = job_match.group(1)
        elif comic_match:
            job_id = comic_match.group(1)
        
        if not job_id:
            continue
            
        if job_id not in jobs:
            jobs[job_id] = {
                "job_id": job_id,
                "start_time": None,
                "end_time": None,
                "steps": [],
                "duration_seconds": None,
                "status": "unknown"
            }
        
        job = jobs[job_id]
        
        # Detect start of rendering
        if "Starting" in message and "render" in message.lower():
            job["start_time"] = timestamp
            job["steps"].append({"time": timestamp, "step": "render_start", "message": message})
        
        # Detect render completion
        if "render DONE" in message or "render done" in message.lower():
            job["end_time"] = timestamp
            job["status"] = "completed"
            
            # Extract duration from message if available
            duration_match = re.search(r'in\s+([\d.]+)s', message)
            if duration_match:
                job["duration_seconds"] = float(duration_match.group(1))
            
            job["steps"].append({"time": timestamp, "step": "render_complete", "message": message})
        
        # Detect Smart Crop
        if "Smart Crop" in message:
            job["steps"].append({"time": timestamp, "step": "smart_crop", "message": message})
        
        # Detect Video generation
        if "Video" in message and ("generated" in message or "uploaded" in message):
            job["steps"].append({"time": timestamp, "step": "video", "message": message})
            if "saved" in message.lower() or "uploaded" in message.lower():
                job["status"] = "completed"
        
        # Detect failures
        if "failed" in message.lower() or "error" in message.lower():
            job["status"] = "failed"
            job["steps"].append({"time": timestamp, "step": "error", "message": message})
    
    # Calculate durations for jobs without explicit duration
    for job_id, job in jobs.items():
        if job["start_time"] and job["end_time"] and not job["duration_seconds"]:
            try:
                start = datetime.fromisoformat(job["start_time"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(job["end_time"].replace("Z", "+00:00"))
                job["duration_seconds"] = (end - start).total_seconds()
            except:
                pass
    
    return jobs


@router.get("/logs")
async def get_cloud_logs(
    service: str = Query("nanobanana-backend", description="Service name"),
    severity: str = Query("INFO", description="Minimum severity"),
    limit: int = Query(50, ge=1, le=200),
    hours: int = Query(24, ge=1, le=168, description="Hours to look back")
):
    """
    Fetch logs from Google Cloud Logging.
    """
    
    if not CLOUD_LOGGING_AVAILABLE:
        # Return mock data for local testing
        return {
            "success": True,
            "source": "mock",
            "entries": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "severity": "INFO",
                    "message": "Cloud Logging not available in local environment",
                    "service": service
                }
            ],
            "count": 1
        }
    
    try:
        client = cloud_logging.Client()
        
        # Build filter
        time_filter = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
        
        filter_str = f'''
            resource.type="cloud_run_revision"
            resource.labels.service_name="{service}"
            timestamp>="{time_filter}"
            severity>={severity}
        '''
        
        entries = []
        for entry in client.list_entries(
            filter_=filter_str,
            order_by=DESCENDING,
            max_results=limit
        ):
            entries.append({
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "severity": entry.severity or "DEFAULT",
                "message": entry.payload if isinstance(entry.payload, str) else str(entry.payload),
                "service": service,
                "insert_id": entry.insert_id
            })
        
        return {
            "success": True,
            "source": "cloud_logging",
            "entries": entries,
            "count": len(entries)
        }
        
    except Exception as e:
        logger.exception("Failed to fetch Cloud Logs")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/performance")
async def get_performance_metrics(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=10, le=500)
):
    """
    Analyze logs to extract performance metrics for comic generation.
    Returns timing data for each job/comic.
    """
    
    if not CLOUD_LOGGING_AVAILABLE:
        # Return sample mock data
        return {
            "success": True,
            "source": "mock",
            "summary": {
                "total_jobs": 3,
                "completed": 2,
                "failed": 1,
                "avg_duration_seconds": 95.5,
                "min_duration_seconds": 78.2,
                "max_duration_seconds": 112.8
            },
            "jobs": [
                {
                    "job_id": "122",
                    "status": "completed",
                    "duration_seconds": 95.5,
                    "start_time": "2026-01-10T16:30:00Z",
                    "end_time": "2026-01-10T16:31:35Z",
                    "steps": []
                }
            ]
        }
    
    try:
        client = cloud_logging.Client()
        
        time_filter = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
        
        # Query for render-related logs
        filter_str = f'''
            resource.type="cloud_run_revision"
            timestamp>="{time_filter}"
            (textPayload=~"render" OR textPayload=~"Video" OR textPayload=~"Smart Crop" OR textPayload=~"JOB")
        '''
        
        entries = []
        for entry in client.list_entries(
            filter_=filter_str,
            order_by=DESCENDING,
            max_results=limit
        ):
            entries.append({
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "severity": entry.severity or "DEFAULT",
                "message": entry.payload if isinstance(entry.payload, str) else str(entry.payload),
            })
        
        # Analyze logs
        jobs = parse_log_for_performance(entries)
        
        # Calculate summary stats
        completed_jobs = [j for j in jobs.values() if j["status"] == "completed" and j["duration_seconds"]]
        failed_jobs = [j for j in jobs.values() if j["status"] == "failed"]
        
        durations = [j["duration_seconds"] for j in completed_jobs if j["duration_seconds"]]
        
        summary = {
            "total_jobs": len(jobs),
            "completed": len(completed_jobs),
            "failed": len(failed_jobs),
            "avg_duration_seconds": round(sum(durations) / len(durations), 1) if durations else None,
            "min_duration_seconds": round(min(durations), 1) if durations else None,
            "max_duration_seconds": round(max(durations), 1) if durations else None
        }
        
        # Sort jobs by start time (most recent first)
        sorted_jobs = sorted(
            jobs.values(), 
            key=lambda x: x.get("start_time") or "", 
            reverse=True
        )
        
        return {
            "success": True,
            "source": "cloud_logging",
            "summary": summary,
            "jobs": sorted_jobs[:20]  # Return top 20
        }
        
    except Exception as e:
        logger.exception("Failed to analyze performance")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/video")
async def get_video_generation_logs(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=10, le=200)
):
    """
    Get video generation specific logs.
    """
    
    if not CLOUD_LOGGING_AVAILABLE:
        return {
            "success": True,
            "source": "mock",
            "entries": [],
            "count": 0
        }
    
    try:
        client = cloud_logging.Client()
        
        time_filter = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
        
        filter_str = f'''
            resource.type="cloud_run_revision"
            timestamp>="{time_filter}"
            textPayload=~"[Vv]ideo"
        '''
        
        entries = []
        for entry in client.list_entries(
            filter_=filter_str,
            order_by=DESCENDING,
            max_results=limit
        ):
            entries.append({
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "severity": entry.severity or "DEFAULT",
                "message": entry.payload if isinstance(entry.payload, str) else str(entry.payload),
            })
        
        return {
            "success": True,
            "source": "cloud_logging",
            "entries": entries,
            "count": len(entries)
        }
        
    except Exception as e:
        logger.exception("Failed to fetch video logs")
        raise HTTPException(status_code=500, detail=str(e))
