"""
Job Processor Service
Database-driven job queue for reliable comic generation

This service ensures ALL comics are generated successfully by:
1. Polling database for pending jobs
2. Processing jobs in order (by ID ascending)
3. Automatic retry on failure
4. Locking to prevent race conditions
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.models.comic import Comic
from app.models.comic_panel import ComicPanel

logger = logging.getLogger(__name__)

# Configuration
# High-volume production config for handling 1000+ comics efficiently
# With parallel part rendering (2 parts per comic), actual parallel capacity is doubled
# 
# Performance estimates for 1000 comics:
# - 64 parallel comics × 2 parts each = 128 concurrent image generations
# - 1000 comics ÷ 64 per batch = 15.6 batches
# - 15.6 batches × 20 minutes = ~5.2 hours total (vs 83 hours sequential!)
#
# Cloud Run requirements:
# - Recommended: 16+ vCPU, 32GB+ RAM per instance
# - Set max instances to 2-3 for cost control
# - Ensure Vertex AI quota: 300+ requests/minute
JOB_CONFIG = {
    "script": {
        "max_parallel": 32,  # 32 comics generating scripts simultaneously
        "lock_timeout_minutes": 10,
    },
    "image": {
        "max_parallel": 64,  # 64 comics × 2 parts = 128 parallel image generations!
        "lock_timeout_minutes": 20,
    },
    "video": {
        "max_parallel": 8,  # 8 videos at once (less resource intensive)
        "lock_timeout_minutes": 30,
    }
}


def generate_worker_id(prefix: str) -> str:
    """Generate unique worker ID"""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


    # =============================================================================
    # AUTO-RECOVERY FOR STUCK COMICS (TIMEOUT-BASED)
    # =============================================================================

    def recover_stuck_jobs(db: Session) -> Dict[str, Any]:
        """
        Automatic recovery for comics stuck in PROCESSING/RENDERING/other states.
    
        Comics become "stuck" when:
        1. Image generation fails but status doesn't reset
        2. Locks expire but locks remain set
        3. System crashes while job was running
    
        This function:
        - Detects comics locked > timeout_minutes
        - Resets status based on what stage they were in
        - Clears locks to allow retry
        - Logs recovery for audit trail
        """
        recovered = {"script": 0, "image": 0, "video": 0, "total": 0}
    
        # Check SCRIPT jobs that are stuck
        script_timeout = JOB_CONFIG["script"]["lock_timeout_minutes"]
        script_expiry = datetime.now() - timedelta(minutes=script_timeout)
    
        stuck_scripts = db.query(Comic).filter(
            and_(
                Comic.draft_job_status.in_(['SCRIPT_FAILED', 'PENDING']),
                Comic.locked_by.isnot(None),
                Comic.locked_at < script_expiry
            )
        ).all()
    
        for comic in stuck_scripts:
            Process all types of jobs in one call.
            comic.locked_at = None
            comic.script_retry_count = (comic.script_retry_count or 0) + 1
            recovered["script"] += 1
            logger.warning(f"🔓 AUTO-RECOVER: Unlocked stuck SCRIPT job for comic #{comic.id} (retry #{comic.script_retry_count})")
    
        # Check IMAGE jobs that are stuck
        image_timeout = JOB_CONFIG["image"]["lock_timeout_minutes"]
        image_expiry = datetime.now() - timedelta(minutes=image_timeout)
    
        stuck_images = db.query(Comic).filter(
            and_(
                Comic.draft_job_status.in_(['PROCESSING', 'RENDERING']),
                Comic.locked_by.isnot(None),
                Comic.locked_at < image_expiry
            )
        ).all()
    
        for comic in stuck_images:
            comic.draft_job_status = 'SCRIPT_READY'  # Reset for retry
        def process_all_jobs(db: Session) -> Dict[str, Any]:
            """
            Process all types of jobs in one call.
    
            Auto-recovery runs FIRST to recover any stuck comics before processing.
            """
            # RUN AUTO-RECOVERY FIRST to recover any stuck comics
            logger.info("=" * 80)
            logger.info("🔄 Starting auto-recovery for stuck comics...")
            recovery_stats = recover_stuck_jobs(db)
            logger.info(f"✅ Auto-recovery complete: {recovery_stats}")
            logger.info("=" * 80)
    
            # Now process new jobs
            results = {
                "recovery": recovery_stats,
                "script": process_script_jobs(db),
                "image": process_image_jobs(db),
                "video": process_video_jobs(db),
            }
    
            return results
            comic.locked_by = None
            comic.locked_at = None
            comic.image_retry_count = (comic.image_retry_count or 0) + 1
            comic.last_error_message = f"Auto-recovered from stuck RENDERING after {image_timeout}min timeout (retry #{comic.image_retry_count})"
            comic.last_error_at = datetime.now()
            recovered["image"] += 1
            logger.warning(f"🔓 AUTO-RECOVER: Reset stuck IMAGE job for comic #{comic.id} to SCRIPT_READY (retry #{comic.image_retry_count})")
    
        # Check VIDEO jobs that are stuck
        video_timeout = JOB_CONFIG["video"]["lock_timeout_minutes"]
        video_expiry = datetime.now() - timedelta(minutes=video_timeout)
    
        stuck_videos = db.query(Comic).filter(
            and_(
                Comic.draft_job_status == 'PROCESSING',
                Comic.locked_by.isnot(None),
                Comic.locked_at < video_expiry,
                Comic.cover_url.isnot(None)  # Images were done
            )
        ).all()
    
        for comic in stuck_videos:
            # For video, keep at PROCESSING but clear lock for retry
            comic.locked_by = None
            comic.locked_at = None
            comic.video_retry_count = (comic.video_retry_count or 0) + 1
            comic.last_error_message = f"Auto-recovered from stuck VIDEO after {video_timeout}min timeout (retry #{comic.video_retry_count})"
            comic.last_error_at = datetime.now()
            recovered["video"] += 1
            logger.warning(f"🔓 AUTO-RECOVER: Unlocked stuck VIDEO job for comic #{comic.id} (retry #{comic.video_retry_count})")
    
        if recovered["script"] + recovered["image"] + recovered["video"] > 0:
            db.commit()
            recovered["total"] = recovered["script"] + recovered["image"] + recovered["video"]
            logger.warning(f"🔓 AUTO-RECOVERY SUMMARY: {recovered['total']} comics recovered ({recovered['script']} script, {recovered['image']} image, {recovered['video']} video)")
    
        return recovered


def is_lock_expired(locked_at: datetime, timeout_minutes: int) -> bool:
    """Check if a lock has expired"""
    if not locked_at:
        return True
    expiry = locked_at + timedelta(minutes=timeout_minutes)
    return datetime.now() > expiry


# =============================================================================
# SCRIPT JOBS PROCESSOR
# =============================================================================

def get_pending_script_jobs(db: Session, limit: int = 4) -> List[Comic]:
    """
    Get comics that need script generation/retry
    
    Conditions:
    - Status = PENDING or SCRIPT_FAILED
    - Not locked OR lock expired
    """
    timeout = JOB_CONFIG["script"]["lock_timeout_minutes"]
    lock_expiry = datetime.now() - timedelta(minutes=timeout)
    
        Dict with processed, success, failed counts
    """
    worker_id = generate_worker_id("script")
    limit = JOB_CONFIG["script"]["max_parallel"]
    
    logger.info(f"[{worker_id}] Starting PARALLEL script job processing (max {limit})...")
    
    # Get pending jobs
    jobs = get_pending_script_jobs(db, limit)
    
    if not jobs:
        logger.info(f"[{worker_id}] No pending script jobs found")
        return {"processed": 0, "success": 0, "failed": 0}
    
    results = {"processed": 0, "success": 0, "failed": 0, "jobs": []}
    
    def process_single_script(comic: Comic):
        """Process script generation for a single comic in thread"""
        # Create new DB session for thread safety
        from app.core.database import SessionLocal
        thread_db = SessionLocal()
        
        try:
            # Re-query comic in this thread's session
            comic_id = comic.id
            comic = thread_db.query(Comic).filter(Comic.id == comic_id).first()
            if not comic:
                return {"comic_id": comic_id, "status": "not_found"}

            job_result = {"comic_id": comic.id, "status": "pending"}

            logger.info(f"[{worker_id}] Thread locked comic #{comic.id} (status: pending)")
            # Lock the job
            comic.locked_by = worker_id
            comic.locked_at = datetime.now()
            comic.draft_job_status = 'GENERATING_SCRIPT'
            comic.script_started_at = datetime.now()
            thread_db.commit()
            
            logger.info(f"[{worker_id}] Processing script for comic #{comic.id}")
            
            # Import core and generate script
            import sys
            from pathlib import Path
            ROOT_DIR = Path(__file__).resolve().parent.parent.parent
            if str(ROOT_DIR) not in sys.path:
                sys.path.append(str(ROOT_DIR))
            
            import core
            
            # Get style and genre info
            from app.models.master_data import Style
            style = thread_db.query(Style).filter(Style.id == int(comic.style or 1)).first()
            style_id_str = comic.style or "1"
            genre_ids = comic.genre if isinstance(comic.genre, list) else ["1"]

            # DEBUG: Log what we're using for script generation
            logger.info(f"🎨 Comic #{comic.id} - Style from DB: {style_id_str}, Genres from DB: {genre_ids}")

            # Map DB values to core style/nuance keys for consistency
            try:
                from app.models.master_data import Style, Genre

                style_name = None
                if str(style_id_str).isdigit() and str(style_id_str) not in core.COMIC_STYLES:
                    style_row = thread_db.query(Style).filter(Style.id == int(style_id_str)).first()
                    style_name = style_row.name if style_row else None
                else:
                    style_name = str(style_id_str)

                genre_names: List[str] = []
                numeric_genres = [int(g) for g in genre_ids if str(g).isdigit()]
                if numeric_genres:
                    genre_rows = thread_db.query(Genre).filter(Genre.id.in_(numeric_genres)).all()
                    genre_names = [g.name for g in genre_rows]
                else:
                    genre_names = [str(g) for g in genre_ids]

                mapped_style_id = core.map_style_id(style_id_str, style_name)
                mapped_genres = core.map_nuance_ids(
                    nuance_ids=[str(g) for g in genre_ids],
                    nuance_names=genre_names,
                )
            except Exception:
                mapped_style_id = str(style_id_str or "1")
                mapped_genres = [str(g) for g in genre_ids]
            
            # DEBUG: Log mapped values for script generation
            logger.info(f"🎨 Comic #{comic.id} - Mapped for script: style={mapped_style_id}, nuances={mapped_genres}")
            
            # Generate script
            script = core.make_two_part_script(
                comic.story_idea or "A short comic story",
                mapped_style_id,
                mapped_genres
            )
            
            # Clear existing panels
            thread_db.query(ComicPanel).filter(ComicPanel.comic_id == comic.id).delete()
            
            # Save script as draft panels
            panel_counter = 0
            parts = script.get("parts", [])
            
            for part in parts:
                if not part or not isinstance(part, dict):
                    continue
                part_no = int(part.get("part_no", 0))
                if part_no not in (1, 2):
                    continue
                panels_script = part.get("panels", [])
                
                for i, panel_data in enumerate(panels_script):
                    panel = ComicPanel(
                        comic_id=comic.id,
                        page_number=part_no,
                        panel_number=i + 1,
                        image_url=None,
                        description=panel_data.get("panel_context") or panel_data.get("description"),
                        page_description=panel_data.get("panel_context"),
                        narration=panel_data.get("narration"),
                        page_narration=panel_data.get("narration"),
                        dialogues=panel_data.get("dialogues", []),
                        instruksi_visual=panel_data.get("instruksi_visual"),
                        instruksi_render_teks=panel_data.get("instruksi_render_teks"),
                    )
                    thread_db.add(panel)
                    panel_counter += 1
            
            # Extract metadata
            global_data = script.get("global", {})
            ai_title = (global_data.get("comic_title") or script.get("suggested_title") or "").strip()
            
            # Update comic
            comic.draft_job_status = 'SCRIPT_READY'
            comic.script_completed_at = datetime.now()
            comic.script_retry_count = 0  # Reset on success
            comic.locked_by = None
            comic.locked_at = None
            comic.title = ai_title or (comic.story_idea[:100] if comic.story_idea else "Untitled")
            
            thread_db.commit()
            
            job_result["status"] = "success"
            job_result["panels"] = panel_counter
            
            logger.info(f"[{worker_id}] Thread completed: Comic #{comic.id} script generated ({panel_counter} panels)")
            
            return job_result
            
        except Exception as e:
            logger.error(f"[{worker_id}] Thread failed: Script generation for comic #{comic.id}: {e}")
            
            # Update failure status
            comic.draft_job_status = 'SCRIPT_FAILED'
            comic.script_retry_count = (comic.script_retry_count or 0) + 1
            comic.last_error_message = str(e)[:1000]
            comic.last_error_at = datetime.now()
            comic.locked_by = None
            comic.locked_at = None
            thread_db.commit()
            
            job_result["status"] = "failed"
            job_result["error"] = str(e)[:200]
            
            return job_result
        finally:
            thread_db.close()
    
    # Execute all scripts in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(limit, len(jobs))) as executor:
        future_to_comic = {executor.submit(process_single_script, comic): comic for comic in jobs}
        
        for future in as_completed(future_to_comic):
            comic = future_to_comic[future]
            try:
                job_result = future.result()
                results["jobs"].append(job_result)
                results["processed"] += 1
                
                if job_result.get("status") == "success":
                    results["success"] += 1
                    logger.info(f"[{worker_id}] OK: Comic #{comic.id} script success")
                else:
                    results["failed"] += 1
                    logger.info(f"[{worker_id}] FAIL: Comic #{comic.id} script failed")
            except Exception as e:
                logger.error(f"[{worker_id}] Unexpected error for comic #{comic.id}: {e}")
                results["failed"] += 1
                results["processed"] += 1
    
    logger.info(f"[{worker_id}] Script processing complete: {results['success']} success, {results['failed']} failed")
    return results


# =============================================================================
# IMAGE JOBS PROCESSOR
# =============================================================================

def get_pending_image_jobs(db: Session, limit: int = 4) -> List[Comic]:
    """
    Get comics that need image generation
    
    Conditions:
    - Status = SCRIPT_READY
    - cover_url is NULL
    - Not locked OR lock expired
    """
    timeout = JOB_CONFIG["image"]["lock_timeout_minutes"]
    lock_expiry = datetime.now() - timedelta(minutes=timeout)
    
    jobs = db.query(Comic).filter(
        and_(
            Comic.draft_job_status == 'SCRIPT_READY',
            Comic.cover_url.is_(None),
            or_(
                Comic.locked_by.is_(None),
                Comic.locked_at < lock_expiry
            )
        )
    ).order_by(Comic.id.asc()).limit(limit).all()
    
    return jobs


def process_image_jobs(db: Session) -> Dict[str, Any]:
    """
    Process pending image generation jobs
    """
    worker_id = generate_worker_id("image")
    limit = JOB_CONFIG["image"]["max_parallel"]
    
    logger.info(f"[{worker_id}] Starting image job processing (max {limit})...")
    
    jobs = get_pending_image_jobs(db, limit)
    
    if not jobs:
        logger.info(f"[{worker_id}] No pending image jobs found")
        return {"processed": 0, "success": 0, "failed": 0}
    
    results = {"processed": 0, "success": 0, "failed": 0, "jobs": []}
    
    for comic in jobs:
        job_result = {"comic_id": comic.id, "status": "pending"}
        
        try:
            # Lock the job
            comic.locked_by = worker_id
            comic.locked_at = datetime.now()
            comic.draft_job_status = 'RENDERING'
            comic.render_started_at = datetime.now()
            db.commit()
            
            logger.info(f"[{worker_id}] Rendering images for comic #{comic.id}")
            
            # Import core
            import sys
            from pathlib import Path
            ROOT_DIR = Path(__file__).resolve().parent.parent.parent
            if str(ROOT_DIR) not in sys.path:
                sys.path.append(str(ROOT_DIR))
            
            import core
            
            # Get panels from DB to build script
            panels = db.query(ComicPanel).filter(
                ComicPanel.comic_id == comic.id
            ).order_by(ComicPanel.page_number, ComicPanel.panel_number).all()
            
            # Validate panels - check for invalid data (including negative numbers)
            valid_panels = []
            has_invalid = False
            for p in panels:
                if not p.panel_number or p.panel_number < 1 or p.panel_number > 9:
                    has_invalid = True
                    logger.warning(f"[{worker_id}] Comic #{comic.id} has invalid panel_number: {p.panel_number}")
                elif p.page_number not in (1, 2):
                    has_invalid = True
                    logger.warning(f"[{worker_id}] Comic #{comic.id} has invalid page_number: {p.page_number}")
                else:
                    valid_panels.append(p)
            
            if has_invalid or len(valid_panels) < 9:  # Need at least 9 panels (minimum 1 part)
                logger.warning(f"[{worker_id}] Comic #{comic.id} has invalid panels ({len(valid_panels)} valid, has_invalid={has_invalid}). Deleting and regenerating script...")
                
                # Delete all corrupt panels
                db.query(ComicPanel).filter(ComicPanel.comic_id == comic.id).delete()
                
                # Reset to PENDING to regenerate script
                comic.draft_job_status = 'PENDING'
                comic.locked_by = None
                comic.locked_at = None
                db.commit()
                
                results["failed"] += 1
                job_result["status"] = "reset"
                job_result["error"] = f"Invalid panels deleted, reset to PENDING for script regen"
                results["processed"] += 1
                results["jobs"].append(job_result)
                continue
            
            panels = valid_panels
            
            # Build script structure for core.render_part_payload
            script = {
                "global": {},
                "parts": []
            }
            
            # Group panels by page/part
            part1_panels = [p for p in panels if p.page_number == 1]
            part2_panels = [p for p in panels if p.page_number == 2]
            
            for part_no, part_panels in [(1, part1_panels), (2, part2_panels)]:
                part_data = {
                    "part_no": part_no,
                    "panels": []
                }
                for p in part_panels:
                    part_data["panels"].append({
                        "panel_no": p.panel_number,
                        "panel_title": "",
                        "panel_context": p.description or p.page_description,
                        "narration": p.narration or p.page_narration,
                        "dialogues": p.dialogues or [],
                        "instruksi_visual": p.instruksi_visual,
                        "instruksi_render_teks": p.instruksi_render_teks,
                    })
                script["parts"].append(part_data)
            
            # Render both parts IN PARALLEL using ThreadPoolExecutor
            all_panel_urls = []
            
            logger.info(f"[{worker_id}] Starting PARALLEL rendering of Part 1 & Part 2 for comic #{comic.id}")
            
            def render_part(part_no: int):
                """Helper function to render a single part in thread"""
                logger.info(f"[{worker_id}] Thread started: Rendering part {part_no} for comic #{comic.id}")
                try:
                    part_result = core.render_part_payload(
                        script=script,
                        part_no=part_no,
                        job_id=str(comic.id),
                        style=comic.style
                    )
                    logger.info(f"[{worker_id}] Thread completed: Part {part_no} for comic #{comic.id}")
                    return (part_no, part_result)
                except Exception as e:
                    logger.error(f"[{worker_id}] Thread failed: Part {part_no} for comic #{comic.id} - {e}")
                    raise
            
            # Execute both parts in parallel
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit both render tasks
                future_to_part = {executor.submit(render_part, part_no): part_no for part_no in [1, 2]}
                
                # Collect results as they complete
                part_results = {}
                for future in as_completed(future_to_part):
                    part_no = future_to_part[future]
                    try:
                        part_no_result, part_result = future.result()
                        part_results[part_no_result] = part_result
                        logger.info(f"[{worker_id}] OK: Part {part_no_result} completed successfully")
                    except Exception as e:
                        logger.error(f"[{worker_id}] FAIL: Part {part_no} failed: {e}")
                        raise  # Re-raise to trigger failure handling
            
            logger.info(f"[{worker_id}] PARALLEL rendering complete for comic #{comic.id}")
            
            # Save panel URLs to database (process in order: Part 1 then Part 2)
            for part_no in [1, 2]:
                part_result = part_results.get(part_no, {})
                panel_urls = part_result.get("panel_urls", [])
                
                part_panels = part1_panels if part_no == 1 else part2_panels
                for i, url in enumerate(panel_urls):
                    if url and i < len(part_panels):
                        part_panels[i].image_url = url
                        all_panel_urls.append(url)
            
            db.commit()
            
            # Update comic
            comic.render_completed_at = datetime.now()
            comic.clipping_started_at = datetime.now()
            comic.clipping_completed_at = datetime.now()
            comic.draft_job_status = 'PROCESSING'  # Ready for video
            comic.image_retry_count = 0  # Reset on success
            comic.locked_by = None
            comic.locked_at = None
            
            # Set cover from first panel
            if all_panel_urls:
                comic.cover_url = all_panel_urls[0]
            
            db.commit()
            
            results["success"] += 1
            job_result["status"] = "success"
            job_result["panels"] = len(all_panel_urls)
            
            logger.info(f"[{worker_id}] Comic #{comic.id} images rendered ({len(all_panel_urls)} panels)")
            
        except Exception as e:
            logger.error(f"[{worker_id}] Image generation failed for comic #{comic.id}: {e}")
            import traceback
            traceback.print_exc()
            
            # Update failure status - go back to SCRIPT_READY for retry
            comic.draft_job_status = 'SCRIPT_READY'
            comic.image_retry_count = (comic.image_retry_count or 0) + 1
            comic.last_error_message = str(e)[:1000]
            comic.last_error_at = datetime.now()
            comic.locked_by = None
            comic.locked_at = None
            db.commit()
            
            results["failed"] += 1
            job_result["status"] = "failed"
            job_result["error"] = str(e)[:200]
        
        results["processed"] += 1
        results["jobs"].append(job_result)
    
    logger.info(f"[{worker_id}] Image processing complete: {results['success']} success, {results['failed']} failed")
    return results


# =============================================================================
# VIDEO JOBS PROCESSOR
# =============================================================================

def get_pending_video_jobs(db: Session, limit: int = 1) -> List[Comic]:
    """
    Get comics that need video generation
    
    Conditions:
    - Status = PROCESSING (images done, waiting for video)
    - cover_url is NOT NULL (images exist)
    - preview_video_url is NULL (video not generated)
    - Not locked OR lock expired
    """
    timeout = JOB_CONFIG["video"]["lock_timeout_minutes"]
    lock_expiry = datetime.now() - timedelta(minutes=timeout)
    
    # Enforce global concurrency limit for videos (async tasks)
    busy_count = db.query(Comic).filter(
        Comic.draft_job_status == 'PROCESSING',
        Comic.locked_by.isnot(None),
        Comic.locked_at >= lock_expiry
    ).count()
    
    if busy_count >= limit:
        logger.info(f"Video queue full ({busy_count} active >= limit {limit}), skipping pickup")
        return []
    
    jobs = db.query(Comic).filter(
        and_(
            Comic.draft_job_status == 'PROCESSING',
            Comic.cover_url.isnot(None),
            Comic.preview_video_url.is_(None),
            or_(
                Comic.locked_by.is_(None),
                Comic.locked_at < lock_expiry
            )
        )
    ).order_by(Comic.id.asc()).limit(limit).all()
    
    return jobs


def process_video_jobs(db: Session) -> Dict[str, Any]:
    """
    Process pending video generation jobs using ThreadPoolExecutor for parallel processing
    
    Returns:
        Dict with processed, success, failed counts
    """
    worker_id = generate_worker_id("video")
    limit = JOB_CONFIG["video"]["max_parallel"]
    
    logger.info(f"[{worker_id}] Starting PARALLEL video job processing (max {limit})...")
    
    jobs = get_pending_video_jobs(db, limit)
    
    if not jobs:
        logger.info(f"[{worker_id}] No pending video jobs found")
        return {"processed": 0, "success": 0, "failed": 0}
    
    results = {"processed": 0, "success": 0, "failed": 0, "jobs": []}
    
    def process_single_video(comic: Comic):
        """Process video generation for a single comic in thread"""
        # Create new DB session for thread safety
        from app.core.database import SessionLocal
        thread_db = SessionLocal()
        
        try:
            # Re-query comic in this thread's session
            comic = thread_db.query(Comic).filter(Comic.id == comic.id).first()
            if not comic:
                return {"comic_id": comic.id, "status": "not_found"}
            
            job_result = {"comic_id": comic.id, "status": "pending"}
            
            # Lock the job
            comic.locked_by = worker_id
            comic.locked_at = datetime.now()
            comic.video_started_at = datetime.now()
            thread_db.commit()
            
            logger.info(f"[{worker_id}] Thread generating video for comic #{comic.id}")
            
            # Get all panels
            panels = thread_db.query(ComicPanel).filter(
                ComicPanel.comic_id == comic.id,
                ComicPanel.image_url.isnot(None)
            ).order_by(ComicPanel.page_number, ComicPanel.panel_number).all()
            
            if not panels:
                raise Exception("No panels with images found")
            
            # Build panels data for video generation
            panels_data = [{
                "image_url": p.image_url,
                "narration": p.narration or p.page_narration or "",
                "dialogue": p.dialogues or [],
                "description": p.description or p.page_description or ""
            } for p in panels]
            
            # Import video generation
            import sys
            from pathlib import Path
            ROOT_DIR = Path(__file__).resolve().parent.parent.parent
            if str(ROOT_DIR) not in sys.path:
                sys.path.append(str(ROOT_DIR))
            
            # Try to use video generation module
            try:
                from app.services.video_generation import generate_video_from_panels
                video_url = generate_video_from_panels(comic.id, panels_data)
            except ImportError:
                # Fallback: queue to video worker
                from app.services.video_queue import queue_video_generation
                task_name = queue_video_generation(comic.id, panels_data)
                
                if task_name:
                    logger.info(f"[{worker_id}] Video queued to worker for comic #{comic.id}")
                    # Keep status as PROCESSING and KEEP LOCKED to enforce concurrency limit
                    thread_db.commit()
                    
                    job_result["status"] = "queued"
                    job_result["task"] = task_name
                    return job_result
                else:
                    raise Exception("Failed to queue video generation")
            
            # If we got video_url directly
            comic.preview_video_url = video_url
            comic.video_completed_at = datetime.now()
            comic.draft_job_status = 'COMPLETED'
            comic.video_retry_count = 0  # Reset on success
            comic.locked_by = None
            comic.locked_at = None
            thread_db.commit()
            
            job_result["status"] = "success"
            job_result["video_url"] = video_url[:100] if video_url else None
            
            logger.info(f"[{worker_id}] Thread completed: Comic #{comic.id} video generated")
            
            return job_result
            
        except Exception as e:
            logger.error(f"[{worker_id}] Thread failed: Video generation for comic #{comic.id}: {e}")
            import traceback
            traceback.print_exc()
            
            # Update failure status - stay at PROCESSING for retry
            comic.video_retry_count = (comic.video_retry_count or 0) + 1
            comic.last_error_message = str(e)[:1000]
            comic.last_error_at = datetime.now()
            comic.locked_by = None
            comic.locked_at = None
            thread_db.commit()
            
            job_result["status"] = "failed"
            job_result["error"] = str(e)[:200]
            
            return job_result
        finally:
            thread_db.close()
    
    # Execute all videos in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(limit, len(jobs))) as executor:
        future_to_comic = {executor.submit(process_single_video, comic): comic for comic in jobs}
        
        for future in as_completed(future_to_comic):
            comic = future_to_comic[future]
            try:
                job_result = future.result()
                results["jobs"].append(job_result)
                results["processed"] += 1
                
                if job_result.get("status") == "success":
                    results["success"] += 1
                    logger.info(f"[{worker_id}] OK: Comic #{comic.id} video success")
                elif job_result.get("status") == "queued":
                    results["success"] += 1  # Count queued as success
                    logger.info(f"[{worker_id}] QUEUED: Comic #{comic.id} video queued")
                else:
                    results["failed"] += 1
                    logger.info(f"[{worker_id}] FAIL: Comic #{comic.id} video failed")
            except Exception as e:
                logger.error(f"[{worker_id}] Unexpected error for comic #{comic.id}: {e}")
                results["failed"] += 1
                results["processed"] += 1
    
    logger.info(f"[{worker_id}] Video processing complete: {results['success']} success, {results['failed']} failed")
    return results


# =============================================================================
# COMBINED PROCESSOR (for single endpoint trigger)
# =============================================================================

def process_all_jobs(db: Session) -> Dict[str, Any]:
    """
    Process all types of jobs in one call
    """
    results = {
        "script": process_script_jobs(db),
        "image": process_image_jobs(db),
        "video": process_video_jobs(db),
    }
    
    return results

    # RUN AUTO-RECOVERY FIRST to recover any stuck comics
    logger.info("=" * 80)
    logger.info("🔄 Starting auto-recovery for stuck comics...")
    recovery_stats = recover_stuck_jobs(db)
    logger.info(f"✅ Auto-recovery complete: {recovery_stats}")
    logger.info("=" * 80)
    
    results = {
        "recovery": recovery_stats,
        "script": process_script_jobs(db),
        "image": process_image_jobs(db),
        "video": process_video_jobs(db),
    }
    
    return results

def process_all_jobs(db: Session) -> Dict[str, Any]:
    """
    Process all types of jobs in one call.
    
    Auto-recovery runs FIRST to recover any stuck comics before processing.
    """
    # RUN AUTO-RECOVERY FIRST to recover any stuck comics
    logger.info("=" * 80)
    logger.info("🔄 Starting auto-recovery for stuck comics...")
    recovery_stats = recover_stuck_jobs(db)
    logger.info(f"✅ Auto-recovery complete: {recovery_stats}")
    logger.info("=" * 80)
    
    # Now process new jobs
    results = {
        "recovery": recovery_stats,
        "script": process_script_jobs(db),
        "image": process_image_jobs(db),
        "video": process_video_jobs(db),
    }
    
    return results


def get_job_queue_status(db: Session) -> Dict[str, Any]:
    """
    Get overall job queue status for monitoring
    """
    # Count by status
    pending_scripts = db.query(Comic).filter(
        or_(
            Comic.draft_job_status == 'PENDING',
            Comic.draft_job_status == 'SCRIPT_FAILED',
            Comic.draft_job_status.is_(None)
        )
    ).count()
    
    pending_images = db.query(Comic).filter(
        Comic.draft_job_status == 'SCRIPT_READY',
        Comic.cover_url.is_(None)
    ).count()
    
    pending_videos = db.query(Comic).filter(
        Comic.draft_job_status == 'PROCESSING',
        Comic.cover_url.isnot(None),
        Comic.preview_video_url.is_(None)
    ).count()
    
    completed = db.query(Comic).filter(
        Comic.draft_job_status == 'COMPLETED'
    ).count()
    
    # Count locked (in progress)
    locked = db.query(Comic).filter(
        Comic.locked_by.isnot(None)
    ).count()
    
    return {
        "queue": {
            "pending_scripts": pending_scripts,
            "pending_images": pending_images,
            "pending_videos": pending_videos,
            "in_progress": locked,
            "completed": completed,
        },
        "total_pending": pending_scripts + pending_images + pending_videos,
    }
