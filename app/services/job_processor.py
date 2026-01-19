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
logger.setLevel(logging.DEBUG)

# Add verbose logging handler if not already added
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Configuration
JOB_CONFIG = {
    "script": {
        "max_parallel": 4,
        "lock_timeout_minutes": 10,
    },
    "image": {
        "max_parallel": 4,
        "lock_timeout_minutes": 20,
    },
    "video": {
        "max_parallel": 1,  # Only 1 video at a time for stability
        "lock_timeout_minutes": 30,
    }
}


def generate_worker_id(prefix: str) -> str:
    """Generate unique worker ID"""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


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
    
    jobs = db.query(Comic).filter(
        and_(
            or_(
                Comic.draft_job_status == 'PENDING',
                Comic.draft_job_status == 'SCRIPT_FAILED',
                Comic.draft_job_status.is_(None)
            ),
            or_(
                Comic.locked_by.is_(None),
                Comic.locked_at < lock_expiry
            )
        )
    ).order_by(Comic.id.asc()).limit(limit).all()
    
    return jobs


def process_script_jobs(db: Session) -> Dict[str, Any]:
    """
    Process pending script generation jobs
    
    Returns:
        Dict with processed, success, failed counts
    """
    worker_id = generate_worker_id("script")
    limit = JOB_CONFIG["script"]["max_parallel"]
    
    logger.info(f"[{worker_id}] ========== STARTING SCRIPT JOB PROCESSING ==========")
    logger.info(f"[{worker_id}] Max parallel jobs: {limit}")
    
    # Get pending jobs
    logger.debug(f"[{worker_id}] Querying database for pending jobs...")
    jobs = get_pending_script_jobs(db, limit)
    logger.info(f"[{worker_id}] Found {len(jobs) if jobs else 0} pending jobs")
    
    if not jobs:
        logger.info(f"[{worker_id}] No pending script jobs found - exiting")
        return {"processed": 0, "success": 0, "failed": 0}
    
    results = {"processed": 0, "success": 0, "failed": 0, "jobs": []}
    
    for comic in jobs:
        job_result = {"comic_id": comic.id, "status": "pending"}
        
        try:
            logger.info(f"[{worker_id}] *** Processing comic #{comic.id} ***")
            logger.debug(f"[{worker_id}] Story idea: {comic.story_idea[:50]}...")
            logger.debug(f"[{worker_id}] Style: {comic.style}, Genres: {comic.genre}")
            
            # Lock the job
            comic.locked_by = worker_id
            comic.locked_at = datetime.now()
            comic.draft_job_status = 'GENERATING_SCRIPT'
            comic.script_started_at = datetime.now()
            db.commit()
            logger.debug(f"[{worker_id}] Comic #{comic.id} locked and status set to GENERATING_SCRIPT")
            
            logger.info(f"[{worker_id}] Starting script generation for comic #{comic.id}...")
            
            # Import core and generate script
            import sys
            from pathlib import Path
            ROOT_DIR = Path(__file__).resolve().parent.parent.parent
            if str(ROOT_DIR) not in sys.path:
                sys.path.append(str(ROOT_DIR))
            
            import core
            
            # Get style and genre info
            logger.debug(f"[{worker_id}] Loading style and genre information...")
            from app.models.master_data import Style
            style = db.query(Style).filter(Style.id == int(comic.style or 1)).first()
            style_id_str = comic.style or "1"
            genre_ids = comic.genre if isinstance(comic.genre, list) else ["1"]
            logger.debug(f"[{worker_id}] Style ID: {style_id_str}, Genre IDs: {genre_ids}")

            # Map DB values to core style/nuance keys for consistency
            try:
                from app.models.master_data import Style, Genre
                logger.debug(f"[{worker_id}] Mapping style and genres...")

                style_name = None
                if str(style_id_str).isdigit() and str(style_id_str) not in core.COMIC_STYLES:
                    style_row = db.query(Style).filter(Style.id == int(style_id_str)).first()
                    style_name = style_row.name if style_row else None
                else:
                    style_name = str(style_id_str)

                genre_names: List[str] = []
                numeric_genres = [int(g) for g in genre_ids if str(g).isdigit()]
                if numeric_genres:
                    genre_rows = db.query(Genre).filter(Genre.id.in_(numeric_genres)).all()
                    genre_names = [g.name for g in genre_rows]
                else:
                    genre_names = [str(g) for g in genre_ids]

                mapped_style_id = core.map_style_id(style_id_str, style_name)
                mapped_genres = core.map_nuance_ids(
                    nuance_ids=[str(g) for g in genre_ids],
                    nuance_names=genre_names,
                )
                logger.debug(f"[{worker_id}] Mapped style: {mapped_style_id}, genres: {mapped_genres}")
            except Exception as e:
                logger.error(f"[{worker_id}] Error mapping style/genre: {e}")
                mapped_style_id = str(style_id_str or "1")
                mapped_genres = [str(g) for g in genre_ids]
            
            # Generate script
            logger.info(f"[{worker_id}] === CALLING core.make_two_part_script() ===")
            logger.info(f"[{worker_id}] Story: {comic.story_idea}")
            logger.info(f"[{worker_id}] Style: {mapped_style_id}")
            logger.info(f"[{worker_id}] Genres: {mapped_genres}")
            
            logger.info(f"[{worker_id}] Calling core.make_two_part_script()...")
            script = core.make_two_part_script(
                comic.story_idea or "A short comic story",
                mapped_style_id,
                mapped_genres
            )
            logger.info(f"[{worker_id}] Script generation completed!")
            logger.debug(f"[{worker_id}] Script keys: {script.keys() if isinstance(script, dict) else 'not a dict'}")
            
            # Clear existing panels
            logger.debug(f"[{worker_id}] Clearing existing panels...")
            db.query(ComicPanel).filter(ComicPanel.comic_id == comic.id).delete()
            
            # Save script as draft panels
            panel_counter = 0
            parts = script.get("parts", [])
            logger.info(f"[{worker_id}] Found {len(parts)} parts in script")
            
            for part_idx, part in enumerate(parts):
                if not part or not isinstance(part, dict):
                    logger.debug(f"[{worker_id}] Skipping invalid part {part_idx}")
                    continue
                part_no = int(part.get("part_no", 0))
                if part_no not in (1, 2):
                    logger.debug(f"[{worker_id}] Skipping part with invalid part_no: {part_no}")
                    continue
                    
                panels_script = part.get("panels", [])
                logger.debug(f"[{worker_id}] Part {part_no} has {len(panels_script)} panels")
                
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
                    db.add(panel)
                    panel_counter += 1
            
            logger.info(f"[{worker_id}] Created {panel_counter} panels total")
            
            # Extract metadata
            global_data = script.get("global", {})
            ai_title = (global_data.get("comic_title") or script.get("suggested_title") or "").strip()
            ai_synopsis = (global_data.get("synopsis") or global_data.get("summary") or "").strip()
            
            # Map additional metadata
            comic.theme = global_data.get("theme")
            comic.mood = global_data.get("mood")
            
            # Handle keywords (ensure list)
            raw_keywords = global_data.get("keywords")
            if isinstance(raw_keywords, str):
                comic.keywords = [k.strip() for k in raw_keywords.split(",") if k.strip()]
            elif isinstance(raw_keywords, list):
                comic.keywords = raw_keywords
            else:
                comic.keywords = []
            
            # Update comic
            comic.draft_job_status = 'SCRIPT_READY'
            comic.script_completed_at = datetime.now()
            comic.script_retry_count = 0  # Reset on success
            comic.locked_by = None
            comic.locked_at = None
            comic.title = ai_title or (comic.story_idea[:100] if comic.story_idea else "Untitled")
            
            # Ensure synopsis/summary is populated
            if ai_synopsis:
                comic.synopsis = ai_synopsis
                comic.summary = ai_synopsis
            else:
                # Fallback: Use story idea if AI didn't generate a synopsis
                preview_text = (comic.story_idea or "")[:500]
                if not comic.synopsis:
                    comic.synopsis = preview_text
                if not comic.summary:
                    comic.summary = preview_text

            
            db.commit()
            logger.info(f"[{worker_id}] Database committed for comic #{comic.id}")
            
            results["success"] += 1
            job_result["status"] = "success"
            job_result["panels"] = panel_counter
            
            logger.info(f"[{worker_id}] ✓ Comic #{comic.id} script generated successfully ({panel_counter} panels)")
            logger.info(f"[{worker_id}] Status: {comic.draft_job_status}")
            
        except Exception as e:
            logger.error(f"[{worker_id}] ✗ Script generation FAILED for comic #{comic.id}")
            logger.exception(f"[{worker_id}] Exception details: {e}")
            
            # CRITICAL FIX: Set fallback title even on failure to prevent NULL title errors
            # This ensures frontend always has a title to display
            if not comic.title:
                fallback_title = (comic.story_idea[:80] if comic.story_idea else "Untitled Comic").strip()
                comic.title = fallback_title
                logger.info(f"[{worker_id}] Set fallback title for comic #{comic.id}: '{fallback_title}'")
            
            # Set fallback synopsis/summary if missing
            if not comic.synopsis and comic.story_idea:
                comic.synopsis = comic.story_idea[:500]
            if not comic.summary and comic.story_idea:
                comic.summary = comic.story_idea[:500]
            
            # Update failure status
            comic.draft_job_status = 'SCRIPT_FAILED'
            comic.script_retry_count = (comic.script_retry_count or 0) + 1
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
    
    logger.info(f"[{worker_id}] ========== SCRIPT PROCESSING COMPLETE ==========")
    logger.info(f"[{worker_id}] Results: {results['processed']} processed, {results['success']} success, {results['failed']} failed")
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
                        logger.info(f"[{worker_id}] ✅ Part {part_no_result} completed successfully")
                    except Exception as e:
                        logger.error(f"[{worker_id}] ❌ Part {part_no} failed: {e}")
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
            # MANUAL MODE: Set to COMPLETED immediately (skip auto-video)
            comic.draft_job_status = 'COMPLETED' 
            comic.image_retry_count = 0  # Reset on success
            comic.locked_by = None
            comic.locked_at = None
            
            # Set cover from first panel
            if all_panel_urls:
                comic.cover_url = all_panel_urls[0]

            # DISABLE AUTO-QUEUE for video (Manual Trigger Only)
            # if len(all_panel_urls) >= 18 and comic.preview_video_url is None:
            #     try:
            #         from app.services.video_queue import queue_video_generation
            #
            #         panels_for_video = db.query(ComicPanel).filter(
            #             ComicPanel.comic_id == comic.id,
            #             ComicPanel.image_url.isnot(None)
            #         ).order_by(ComicPanel.page_number, ComicPanel.panel_number).all()
            #
            #         panels_data = [{
            #             "image_url": p.image_url,
            #             "narration": p.narration or p.page_narration or "",
            #             "dialogue": p.dialogues or [],
            #             "description": p.description or p.page_description or ""
            #         } for p in panels_for_video]
            #
            #         task_name = queue_video_generation(
            #             comic.id,
            #             panels_data,
            #             user_id=comic.user_id
            #         )

                    if task_name:
                        logger.info(
                            f"[{worker_id}] Auto-queued video for comic #{comic.id}: {task_name}"
                        )
                    else:
                        logger.warning(
                            f"[{worker_id}] Auto-queue video failed for comic #{comic.id}"
                        )
                except Exception as e:
                    logger.warning(f"[{worker_id}] Auto-queue video error for comic #{comic.id}: {e}")

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
    Process pending video generation jobs
    Only 1 at a time for stability
    """
    worker_id = generate_worker_id("video")
    limit = JOB_CONFIG["video"]["max_parallel"]  # Always 1
    
    logger.info(f"[{worker_id}] Starting video job processing (max {limit})...")
    
    jobs = get_pending_video_jobs(db, limit)
    
    if not jobs:
        logger.info(f"[{worker_id}] No pending video jobs found")
        return {"processed": 0, "success": 0, "failed": 0}
    
    results = {"processed": 0, "success": 0, "failed": 0, "jobs": []}
    
    for comic in jobs:
        job_result = {"comic_id": comic.id, "status": "pending"}
        
        try:
            # Lock the job
            comic.locked_by = worker_id
            comic.locked_at = datetime.now()
            comic.video_started_at = datetime.now()
            db.commit()
            
            logger.info(f"[{worker_id}] Generating video for comic #{comic.id}")
            
            # Get all panels
            panels = db.query(ComicPanel).filter(
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
                    # It will be unlocked by timeout (30m) or when worker updates status to COMPLETED
                    db.commit()
                    
                    results["processed"] += 1
                    job_result["status"] = "queued"
                    job_result["task"] = task_name
                    results["jobs"].append(job_result)
                    continue
                else:
                    raise Exception("Failed to queue video generation")
            
            # If we got video_url directly
            comic.preview_video_url = video_url
            comic.video_completed_at = datetime.now()
            comic.draft_job_status = 'COMPLETED'
            comic.video_retry_count = 0  # Reset on success
            comic.locked_by = None
            comic.locked_at = None
            db.commit()
            
            results["success"] += 1
            job_result["status"] = "success"
            job_result["video_url"] = video_url[:100] if video_url else None
            
            logger.info(f"[{worker_id}] Comic #{comic.id} video generated successfully")
            
        except Exception as e:
            logger.error(f"[{worker_id}] Video generation failed for comic #{comic.id}: {e}")
            import traceback
            traceback.print_exc()
            
            # Update failure status - stay at PROCESSING for retry
            comic.video_retry_count = (comic.video_retry_count or 0) + 1
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
    
    logger.info(f"[{worker_id}] Video processing complete: {results['success']} success, {results['failed']} failed")
    return results


# =============================================================================
# COMBINED PROCESSOR (for single endpoint trigger)
# =============================================================================

def process_all_jobs(db: Session) -> Dict[str, Any]:
    """
    Process all types of jobs in one call
    Includes automatic recovery of failed jobs
    """
    # First, recover any failed jobs
    from app.services.failed_job_recovery import process_failed_job_recovery
    
    results = {
        "recovery": process_failed_job_recovery(db),  # NEW: Auto-recover FAILED comics
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
