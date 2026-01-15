"""
Admin API endpoints for Cloud Logging integration and performance monitoring.
"""

from fastapi import APIRouter, Query, HTTPException, Depends, Body
from typing import Optional, List
from datetime import datetime, timedelta
import logging
import re
import os

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.core.database import get_db

logger = logging.getLogger("admin_api")

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(get_current_admin)]
)

# Temporary router for initial setup (NO AUTH)
setup_router = APIRouter(
    prefix="/api/v1/setup",
    tags=["Setup"]
)


# Lazy loading for Google Cloud Logging
CLOUD_LOGGING_AVAILABLE = None # Will be determined at runtime


def _get_logging_client():
    from google.cloud import logging as cloud_logging
    from google.cloud.logging_v2 import DESCENDING
    return cloud_logging.Client(), DESCENDING


def _get_storage_client():
    from google.cloud import storage
    return storage.Client()


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
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    current_admin: User = Depends(get_current_admin)
):
    """
    Fetch logs from Google Cloud Logging.
    """
    
    # Try to get client
    # Try to get client
    client, DESCENDING = _get_logging_client()
    
    if not client:
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
    limit: int = Query(100, ge=10, le=500),
    current_admin: User = Depends(get_current_admin)
):
    """
    Analyze logs to extract performance metrics for comic generation.
    Returns timing data for each job/comic.
    """
    

    
    try:
        client, DESCENDING = _get_logging_client()
        
        if not client:
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
    limit: int = Query(50, ge=10, le=200),
    current_admin: User = Depends(get_current_admin)
):
    """
    Get video generation specific logs.
    """
    

    
    try:
        client, DESCENDING = _get_logging_client()
        if not client:
             return {
                "success": True,
                "source": "mock",
                "entries": [],
                "count": 0
             }
        
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


@router.get("/comics/generation-stats")
async def get_comic_generation_stats(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin)
):
    """
    Get detailed comic generation statistics with timing breakdown.
    Returns data for monitoring who created comics and how long each step took.
    """
    from app.core.database import get_session_local
    from app.models.comic import Comic
    from app.models.user import User
    from app.models.master_data import Style, Genre
    
    SessionLocal = get_session_local()
    db = SessionLocal()
    
    try:
        # Get comics created in the last N hours
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        comics = db.query(Comic).filter(
            Comic.created_at >= cutoff_time
        ).order_by(Comic.created_at.desc()).limit(limit).all()
        
        results = []
        
        for comic in comics:
            # Get user info
            user = db.query(User).filter(User.id_users == comic.user_id).first()
            user_name = user.full_name if user else f"User {comic.user_id}"
            user_email = user.email if user else None
            
            # Get style name
            style_name = "Unknown"
            if comic.style:
                try:
                    style = db.query(Style).filter(Style.id == int(comic.style)).first()
                    style_name = style.name if style else comic.style
                except:
                    style_name = comic.style
            
            # Get genre names
            genre_names = []
            if comic.genre:
                for genre_id in comic.genre:
                    try:
                        genre = db.query(Genre).filter(Genre.id == int(genre_id)).first()
                        if genre:
                            genre_names.append(genre.name)
                    except:
                        pass
            
            # Calculate durations for each step
            def calc_duration(start, end):
                if start and end:
                    delta = end - start
                    return round(delta.total_seconds(), 1)
                return None
            
            script_duration = calc_duration(comic.script_started_at, comic.script_completed_at)
            render_duration = calc_duration(comic.render_started_at, comic.render_completed_at)
            clipping_duration = calc_duration(comic.clipping_started_at, comic.clipping_completed_at)
            video_duration = calc_duration(comic.video_started_at, comic.video_completed_at)
            
            # Total duration from script start to video complete
            total_duration = None
            if comic.script_started_at and comic.video_completed_at:
                total_duration = calc_duration(comic.script_started_at, comic.video_completed_at)
            elif comic.script_started_at and comic.render_completed_at:
                total_duration = calc_duration(comic.script_started_at, comic.render_completed_at)
            
            results.append({
                "comic_id": comic.id,
                "created_at": comic.created_at.isoformat() if comic.created_at else None,
                "user": {
                    "id": comic.user_id,
                    "name": user_name,
                    "email": user_email
                },
                "title": comic.title or "Untitled",
                "style": style_name,
                "genres": genre_names,
                "story_idea": comic.story_idea[:200] if comic.story_idea else None,
                "status": comic.draft_job_status or "PENDING",
                "timing": {
                    "script": {
                        "started_at": comic.script_started_at.isoformat() if comic.script_started_at else None,
                        "completed_at": comic.script_completed_at.isoformat() if comic.script_completed_at else None,
                        "duration_seconds": script_duration
                    },
                    "render": {
                        "started_at": comic.render_started_at.isoformat() if comic.render_started_at else None,
                        "completed_at": comic.render_completed_at.isoformat() if comic.render_completed_at else None,
                        "duration_seconds": render_duration
                    },
                    "clipping": {
                        "started_at": comic.clipping_started_at.isoformat() if comic.clipping_started_at else None,
                        "completed_at": comic.clipping_completed_at.isoformat() if comic.clipping_completed_at else None,
                        "duration_seconds": clipping_duration
                    },
                    "video": {
                        "started_at": comic.video_started_at.isoformat() if comic.video_started_at else None,
                        "completed_at": comic.video_completed_at.isoformat() if comic.video_completed_at else None,
                        "duration_seconds": video_duration
                    },
                    "total_duration_seconds": total_duration
                }
            })
        
        # Calculate summary stats
        completed = [r for r in results if r["status"] == "COMPLETED"]
        
        def avg_duration(key):
            durations = [r["timing"][key]["duration_seconds"] for r in completed if r["timing"][key]["duration_seconds"]]
            return round(sum(durations) / len(durations), 1) if durations else None
        
        total_durations = [r["timing"]["total_duration_seconds"] for r in completed if r["timing"]["total_duration_seconds"]]
        
        summary = {
            "total_comics": len(results),
            "completed": len(completed),
            "failed": len([r for r in results if r["status"] == "FAILED"]),
            "in_progress": len([r for r in results if r["status"] in ["GENERATING_SCRIPT", "SCRIPT_READY", "RENDERING", "PROCESSING"]]),
            "avg_script_duration": avg_duration("script"),
            "avg_render_duration": avg_duration("render"),
            "avg_clipping_duration": avg_duration("clipping"),
            "avg_video_duration": avg_duration("video"),
            "avg_total_duration": round(sum(total_durations) / len(total_durations), 1) if total_durations else None
        }
        
        return {
            "success": True,
            "summary": summary,
            "comics": results
        }
        
    except Exception as e:
        logger.exception("Failed to get generation stats")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/db-patch-timing")
async def patch_database_timing_columns():
    """
    Manually patch database to include timing columns.
    Run this once after deployment.
    """
    from app.core.database import get_engine
    from sqlalchemy import text
    
    engine = get_engine()
    try:
        with engine.connect() as conn:
            # We use generic text execution.
            # Depending on DB dialect, syntax might slightly differ but TIMESTAMP usually works.
            # Postgres supports TIMESTAMP WITH TIME ZONE. MySQL just TIMESTAMP / DATETIME.
            # Since requirements specify pg8000, we strictly use Postgres syntax.
            
            columns = [
                "script_started_at", "script_completed_at", 
                "render_started_at", "render_completed_at", 
                "clipping_started_at", "clipping_completed_at", 
                "video_started_at", "video_completed_at"
            ]
            
            for col in columns:
                try:
                    conn.execute(text(f"ALTER TABLE comics ADD COLUMN IF NOT EXISTS {col} TIMESTAMP WITH TIME ZONE"))
                except Exception as e:
                    logger.warning(f"Error adding {col}: {e}")
            
            conn.commit()
            return {"success": True, "message": "Timing columns added successfully (or already existed)"}
    except Exception as e:
        logger.exception("DB Patch failed connection")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-users")
async def get_test_users(limit: int = Query(10, ge=1, le=50)):
    """
    Get list of test users for load testing purposes.
    Returns users with phone numbers (no passwords).
    """
    from app.core.database import get_session_local
    from app.models.user import User
    
    SessionLocal = get_session_local()
    db = SessionLocal()
    
    try:
        users = db.query(User).limit(limit).all()
        
        result = []
        for user in users:
            result.append({
                "id": user.id_users,
                "full_name": user.full_name,
                "phone_number": user.phone_number,
                "email": user.email,
                "kredit": user.kredit,
                "is_verified": user.is_verified
            })
        
        return {
            "success": True,
            "users": result,
            "total": len(result),
            "note": "Use phone_number and password to login for load testing"
        }
    except Exception as e:
        logger.exception("Failed to get test users")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/create-test-user")
async def create_test_user(
    phone_number: str = Query(..., description="Phone number for login"),
    password: str = Query("loadtest123", description="Password for login"),
    full_name: str = Query("Load Test User", description="User's full name"),
    kredit: int = Query(10000, description="Initial credits")
):
    """
    Create a new test user for load testing purposes.
    """
    from app.core.database import get_session_local
    from app.models.user import User
    import bcrypt
    import secrets
    
    SessionLocal = get_session_local()
    db = SessionLocal()
    
    try:
        # Check if phone number already exists
        existing = db.query(User).filter(User.phone_number == phone_number).first()
        if existing:
            # Update existing user's credit
            existing.kredit = kredit
            db.commit()
            return {
                "success": True,
                "message": "User already exists, credits updated",
                "user": {
                    "id": existing.id_users,
                    "phone_number": existing.phone_number,
                    "full_name": existing.full_name,
                    "kredit": existing.kredit
                }
            }
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Generate referral code
        referral_code = secrets.token_hex(4).upper()
        
        # Create new user
        new_user = User(
            phone_number=phone_number,
            password=password_hash,
            full_name=full_name,
            kredit=kredit,
            is_verified=True,
            referral_code_id=referral_code,
            role="creator"
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {
            "success": True,
            "message": "Test user created successfully",
            "user": {
                "id": new_user.id_users,
                "phone_number": new_user.phone_number,
                "full_name": new_user.full_name,
                "kredit": new_user.kredit,
                "password": password  # Return plain password for testing
            }
        }
    except Exception as e:
        db.rollback()
        logger.exception("Failed to create test user")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()



@router.post("/comics/{comic_id}/force-fail")
async def force_fail_comic(comic_id: int):
    """
    Force fail a stuck comic job. Useful for clearing stuck jobs in monitoring.
    """
    from app.core.database import get_session_local
    from app.models.comic import Comic
    
    SessionLocal = get_session_local()
    db = SessionLocal()
    
    try:
        comic = db.query(Comic).filter(Comic.id == comic_id).first()
        if not comic:
            raise HTTPException(status_code=404, detail="Comic not found")
            
        previous_status = comic.draft_job_status
        comic.draft_job_status = "FAILED"
        
        db.commit()
        return {
            "success": True, 
            "message": f"Comic {comic_id} forced to FAILED status (was {previous_status})",
            "comic_id": comic_id,
            "previous_status": previous_status,
            "new_status": "FAILED"
        }
    except Exception as e:
        logger.exception(f"Failed to force fail comic {comic_id}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# =============================
# DATABASE ADMIN (SAFE / WHITELISTED)
# =============================
ALLOWED_TABLE_PREVIEW = {
    "users": "id_users",
    "comics": "id",
    "comic_requests": "id",
}


@router.get("/db/tables")
async def list_tables(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    inspector = inspect(db.bind)
    return {"tables": inspector.get_table_names()}


@router.get("/db/preview/{table}")
async def preview_table(
    table: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    if table not in ALLOWED_TABLE_PREVIEW:
        raise HTTPException(status_code=403, detail="Table not allowed")

    pk = ALLOWED_TABLE_PREVIEW[table]
    sql = text(f"SELECT * FROM {table} ORDER BY {pk} DESC LIMIT :limit")
    rows = db.execute(sql, {"limit": limit}).mappings().all()
    rows = [dict(r) for r in rows]
    return {"success": True, "table": table, "rows": rows, "count": len(rows)}


@router.post("/db/update/{table}/{pk_value}")
async def update_row(
    table: str,
    pk_value: int,
    payload: dict = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    if table not in ALLOWED_TABLE_PREVIEW:
        raise HTTPException(status_code=403, detail="Table not allowed")

    pk = ALLOWED_TABLE_PREVIEW[table]
    if not payload:
        raise HTTPException(status_code=400, detail="Empty payload")

    # Build SET clause safely using parameters
    set_clauses = []
    params = {"pk_value": pk_value}
    for idx, (col, val) in enumerate(payload.items()):
        param_key = f"v{idx}"
        set_clauses.append(f"{col} = :{param_key}")
        params[param_key] = val

    set_sql = ", ".join(set_clauses)
    sql = text(f"UPDATE {table} SET {set_sql} WHERE {pk} = :pk_value")

    try:
        db.execute(sql, params)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Failed to update row")
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True, "table": table, "pk": pk_value, "updated_fields": list(payload.keys())}


@router.delete("/db/delete/{table}/{pk_value}")
async def delete_row(
    table: str,
    pk_value: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    if table not in ALLOWED_TABLE_PREVIEW:
        raise HTTPException(status_code=403, detail="Table not allowed")

    pk = ALLOWED_TABLE_PREVIEW[table]
    sql = text(f"DELETE FROM {table} WHERE {pk} = :pk_value")
    try:
        result = db.execute(sql, {"pk_value": pk_value})
        db.commit()
        return {"success": True, "table": table, "pk": pk_value, "deleted": result.rowcount}
    except Exception as e:
        db.rollback()
        logger.exception("Failed to delete row")
        raise HTTPException(status_code=500, detail=str(e))


# =============================
# STORAGE (GCS) ADMIN
# =============================
GCS_BUCKET = os.getenv("GCS_BUCKET_NAME", "mamastoria-storage")


@router.get("/storage/list")
async def list_storage_objects(
    prefix: str = Query("", description="Folder prefix"),
    limit: int = Query(50, ge=1, le=500),
    current_admin: User = Depends(get_current_admin)
):
    client = _get_storage_client()
    bucket = client.bucket(GCS_BUCKET)
    blobs = client.list_blobs(bucket, prefix=prefix, max_results=limit)

    items = []
    for b in blobs:
        items.append({
            "name": b.name,
            "size": b.size,
            "updated": b.updated.isoformat() if b.updated else None,
            "content_type": b.content_type,
            "public_url": b.public_url,
        })

    return {"success": True, "bucket": GCS_BUCKET, "count": len(items), "objects": items}


@router.delete("/storage/delete")
async def delete_storage_object(
    path: str = Query(..., description="Object path to delete"),
    current_admin: User = Depends(get_current_admin)
):
    client = _get_storage_client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(path)
    if not blob.exists():
        raise HTTPException(status_code=404, detail="Object not found")

    try:
        blob.delete()
        return {"success": True, "bucket": GCS_BUCKET, "path": path, "deleted": True}
    except Exception as e:
        logger.exception("Failed to delete object")
        raise HTTPException(status_code=500, detail=str(e))


# =============================
# INITIAL SETUP (NO AUTH) - ONE TIME USE
# =============================
@setup_router.post("/create-initial-admin")
async def create_initial_admin(
    phone_number: str = Query("+6281234567890", description="Phone number for admin"),
    password: str = Query("admin123", description="Password for admin"),
    full_name: str = Query("Admin Dashboard", description="Admin's full name"),
    db: Session = Depends(get_db)
):
    """
    ONE-TIME setup endpoint to create initial admin user.
    NO AUTHENTICATION REQUIRED (use carefully, disable after first use).
    """
    import bcrypt
    import secrets
    from app.models.user import User
    
    try:
        # Check if admin already exists
        existing = db.query(User).filter(User.phone_number == phone_number).first()
        if existing:
            # Update to admin role
            existing.role = "admin"
            existing.kredit = 999999
            existing.is_verified = True
            db.commit()
            return {
                "success": True,
                "message": "User updated to admin role",
                "phone_number": phone_number,
                "password": password,
                "note": "Use these credentials to login to dashboard"
            }
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Generate referral code
        referral_code = secrets.token_hex(4).upper()
        
        # Create new admin user
        new_user = User(
            phone_number=phone_number,
            password=password_hash,
            full_name=full_name,
            kredit=999999,
            is_verified=True,
            referral_code_id=referral_code,
            role="admin"
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {
            "success": True,
            "message": "Admin user created successfully",
            "user_id": new_user.id_users,
            "phone_number": phone_number,
            "password": password,
            "credits": 999999,
            "note": "Use these credentials to login to dashboard"
        }
    except Exception as e:
        db.rollback()
        logger.exception("Failed to create admin")
        raise HTTPException(status_code=500, detail=str(e))
