import logging
import time
import sys
import threading
import traceback
from pathlib import Path
from typing import Optional, Dict, Any
from app.core.database import get_session_local
from app.models.comic import Comic
from app.models.comic_panel import ComicPanel

# Ensure core is importable
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

import core
# We import video_generator inside function or safe level
import video_generator

logger = logging.getLogger(__name__)


def queue_render_to_worker(comic_id: int, script_data: dict, style: str) -> Dict[str, Any]:
    """
    Queue comic rendering to dedicated worker via Cloud Tasks.
    Each part (1 and 2) is queued as a separate job for isolated processing.
    
    This is the NEW recommended approach - uses dedicated worker with dedicated resources.
    Falls back to in-process rendering if queue fails.
    
    Args:
        comic_id: Comic ID in database
        script_data: Full script data for the comic
        style: Style ID
        
    Returns:
        Dict with queue status and task names
    """
    from datetime import datetime
    from app.services.render_queue import queue_both_parts
    
    SessionLocal = get_session_local()
    db = SessionLocal()
    
    try:
        # Update status to RENDERING
        comic = db.query(Comic).filter(Comic.id == comic_id).first()
        if comic:
            comic.draft_job_status = "RENDERING"
            comic.render_started_at = datetime.now()
            db.commit()
        
        # Queue both parts to Cloud Tasks
        logger.info(f"Queuing render jobs for comic {comic_id} to worker...")
        queue_result = queue_both_parts(
            comic_id=comic_id,
            script_data=script_data,
            style=style
        )
        
        if queue_result.get("part1") and queue_result.get("part2"):
            logger.info(f"Successfully queued render jobs for comic {comic_id}")
            return {
                "success": True,
                "queued": True,
                "comic_id": comic_id,
                "tasks": queue_result
            }
        else:
            # Fallback to in-process rendering if queue failed
            logger.warning(f"Queue failed for comic {comic_id}, falling back to in-process rendering")
            
            # Start background thread for in-process rendering
            t = threading.Thread(
                target=render_comic_images_task, 
                args=(comic_id, script_data, style), 
                daemon=True
            )
            t.start()
            
            return {
                "success": True,
                "queued": False,
                "fallback": True,
                "comic_id": comic_id
            }
            
    except Exception as e:
        logger.error(f"Failed to queue render for comic {comic_id}: {e}")
        
        # Fallback to in-process
        t = threading.Thread(
            target=render_comic_images_task, 
            args=(comic_id, script_data, style), 
            daemon=True
        )
        t.start()
        
        return {
            "success": True,
            "queued": False,
            "fallback": True,
            "error": str(e),
            "comic_id": comic_id
        }
    finally:
        db.close()

def render_comic_images_task(comic_id: int, script_data: dict, style: str):
    """Background thread to render comic images from approved draft"""
    # Delay to ensure main transaction commits from the API endpoint
    time.sleep(2)
    
    SessionLocal = get_session_local()
    thread_db = SessionLocal()
    
    try:
        from datetime import datetime
        logger.info(f"Rendering images for comic {comic_id}...")
        
        # Record render start time
        comic_for_timing = thread_db.query(Comic).filter(Comic.id == comic_id).first()
        if comic_for_timing:
            comic_for_timing.render_started_at = datetime.now()
            thread_db.commit()
        
        # Start render job
        core.start_render_all_job(script_data, job_id=str(comic_id))
        
        # Wait for completion (max 15 mins)
        start_time = time.time()
        timeout = 900
        
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError("Rendering timed out")
            
            job_state = core.get_job(str(comic_id))
            if not job_state:
                time.sleep(1)
                continue
            
            job_status = job_state.get("status")
            if job_status == "done":
                logger.info(f"Rendering complete for comic {comic_id}")
                break
            elif job_status == "error":
                raise RuntimeError(f"Render failed: {job_state.get('error')}")
            
            time.sleep(3)
        
        # Record render completion and clipping start
        comic_for_timing = thread_db.query(Comic).filter(Comic.id == comic_id).first()
        if comic_for_timing:
            comic_for_timing.render_completed_at = datetime.now()
            comic_for_timing.clipping_started_at = datetime.now()  # Clipping is part of render
            thread_db.commit()
        
        # Update panel image URLs from GCS
        job_state = core.get_job(str(comic_id))
        cover_url = None
        
        for part_no in [1, 2]:
            part_key = f"part{part_no}"
            if part_key not in job_state:
                continue
            
            part_data = job_state[part_key]
            panel_urls = part_data.get("panel_urls") or []
            panels_count = len(panel_urls)
            
            for panel_idx in range(panels_count):
                # Get GCS URL (or fallback to API preview)
                gcs_url = panel_urls[panel_idx] if panel_idx < len(panel_urls) else None
                image_url = gcs_url or f"/api/preview/{comic_id}/panel/{part_no}/{panel_idx}"
                
                # Panel 1 of Part 1 = Cover
                if part_no == 1 and panel_idx == 0:
                    cover_url = gcs_url
                
                # Update DB panel with image URL
                db_panel = thread_db.query(ComicPanel).filter(
                    ComicPanel.comic_id == comic_id,
                    ComicPanel.page_number == part_no,
                    ComicPanel.panel_number == panel_idx + 1
                ).first()
                
                if db_panel:
                    db_panel.image_url = image_url
        
        # Update comic record with PDF and cover
        comic_record = thread_db.query(Comic).filter(Comic.id == comic_id).first()
        if comic_record:
            logger.info(f"Updating comic {comic_id} with PDF and cover URLs")
            comic_record.pdf_url = f"/api/pdf/{comic_id}"
            comic_record.clipping_completed_at = datetime.now()  # Clipping done
            if cover_url:
                comic_record.cover_url = cover_url
            thread_db.commit()
        else:
            logger.error(f"Comic record {comic_id} not found for status update!")
        
        # Generate PDF
        try:
            core.ensure_job_pdf(str(comic_id))
        except Exception as pdf_err:
            logger.warning(f"PDF generation warning: {pdf_err}")
        
        # Generate Video automatically after images are ready
        video_generated_successfully = False
        try:
            # Get panels with images for video
            panels_for_video = thread_db.query(ComicPanel).filter(
                ComicPanel.comic_id == comic_id,
                ComicPanel.image_url.isnot(None)
            ).order_by(ComicPanel.page_number, ComicPanel.panel_number).all()
            
            logger.info(f"Video generation: Found {len(panels_for_video)} panels for comic {comic_id}")
            
            if panels_for_video:
                panel_data = [{
                    "image_url": p.image_url,
                    "narration": p.narration or p.page_narration or "",
                    "dialogue": p.dialogues or [],
                    "description": p.description or p.page_description or ""
                } for p in panels_for_video]
                
                logger.info(f"Starting video generation for comic {comic_id} with {len(panel_data)} panels...")
                
                # Record video start time
                if comic_record:
                    comic_record.video_started_at = datetime.now()
                    thread_db.commit()
                
                output_path = video_generator.generate_video_for_comic(
                    comic_id=comic_id,
                    panels=panel_data
                )
                
                if output_path:
                    # Update video URL in database
                    logger.info(f"Video output path: {output_path}")
                    if comic_record:
                        comic_record.preview_video_url = output_path
                        comic_record.video_completed_at = datetime.now()  # Video done
                        thread_db.commit()
                    logger.info(f"Video generated and saved for comic {comic_id}: {output_path}")
                    video_generated_successfully = True
                else:
                    logger.error(f"Video generation returned None for comic {comic_id}")
                    raise RuntimeError("Video generation returned None")
            else:
                logger.warning(f"No panels found for video generation for comic {comic_id}")
                raise RuntimeError("No panels found for video generation")
                
        except Exception as video_err:
            logger.exception(f"Video generation FAILED for comic {comic_id}: {video_err}")
            logger.error(f"Video error traceback: {traceback.format_exc()}")
            
            # Update status to FAILED if video generation fails
            if comic_record:
                comic_record.draft_job_status = "FAILED"
                thread_db.commit()
                logger.error(f"Comic {comic_id} status set to FAILED due to video generation error")
            
            # Re-raise to prevent success notification
            raise
        
        # Only reach here if video generation succeeded
        # Update comic status to COMPLETED
        if comic_record and video_generated_successfully:
            logger.info(f"Updating comic {comic_id} status to COMPLETED after successful video generation")
            comic_record.draft_job_status = "COMPLETED"
            thread_db.commit()
            logger.info(f"Comic {comic_id} status committed to DB as COMPLETED")
        
        # Notify user (Database + Push) - Only after video generation succeeds
        try:
            # Re-query comic to ensure user relationship is loaded
            comic_notif = thread_db.query(Comic).filter(Comic.id == comic_id).first()
            if comic_notif:
                from app.models.notification import Notification
                from app.services.push_notification_service import send_push_notification
                
                # Create DB Notification for comic creator
                notif = Notification(
                    user_id=comic_notif.user_id,
                    type="success",
                    title="Komik Selesai! 🎉",
                    message=f"Komik '{comic_notif.title or 'baru'}' sudah siap dibaca. Klik tombol komik saya di profile untuk melihat daftar komik buatanmu.",
                    data=f'{{"comic_id": {comic_id}, "status": "success"}}'
                )
                thread_db.add(notif)
                thread_db.commit()

                # Push Notification via FCM to creator
                if comic_notif.user and comic_notif.user.fcm_token:
                    logger.info(f"Sending push notification to user {comic_notif.user_id}")
                    send_push_notification(
                        fcm_token=comic_notif.user.fcm_token,
                        title="Komik Selesai! 🎉",
                        body=f"Komik '{comic_notif.title or 'baru'}' sudah siap dibaca. Klik tombol komik saya di profile untuk melihat daftar komik buatanmu.",
                        data={"comic_id": str(comic_id), "type": "success"}
                    )
                
                # Notify all followers of the comic creator
                try:
                    from app.models.follow import Follow
                    
                    # Get all followers of the comic creator
                    followers = thread_db.query(Follow).filter(
                        Follow.following_id == comic_notif.user_id
                    ).all()
                    
                    if followers:
                        logger.info(f"Found {len(followers)} followers for user {comic_notif.user_id}")
                        
                        # Get creator name
                        creator_name = comic_notif.user.full_name or comic_notif.user.username or "Seorang kreator"
                        comic_title = comic_notif.title or "komik baru"
                        
                        for follow in followers:
                            try:
                                # Create notification for each follower
                                follower_notif = Notification(
                                    user_id=follow.follower_id,
                                    type="info",
                                    title=f"{creator_name} baru saja membuat karya {comic_title}, yuk baca!",
                                    message=f"{creator_name} baru saja membuat karya {comic_title}, yuk baca!",
                                    data=f'{{"comic_id": {comic_id}, "creator_id": {comic_notif.user_id}}}'
                                )
                                thread_db.add(follower_notif)
                                
                                # Send push notification to follower if they have FCM token
                                from app.models.user import User
                                follower_user = thread_db.query(User).filter(User.id_users == follow.follower_id).first()
                                if follower_user and follower_user.fcm_token:
                                    send_push_notification(
                                        fcm_token=follower_user.fcm_token,
                                        title=f"{creator_name} baru saja membuat karya {comic_title}, yuk baca!",
                                        body=f"{creator_name} baru saja membuat karya {comic_title}, yuk baca!",
                                        data={"comic_id": str(comic_id), "creator_id": str(comic_notif.user_id), "type": "info"}
                                    )
                                    logger.info(f"Sent follower notification to user {follow.follower_id}")
                            except Exception as follower_err:
                                logger.error(f"Failed to notify follower {follow.follower_id}: {follower_err}")
                                continue
                        
                        thread_db.commit()
                        logger.info(f"Sent notifications to {len(followers)} followers")
                    else:
                        logger.info(f"No followers found for user {comic_notif.user_id}")
                        
                except Exception as follower_notif_err:
                    logger.error(f"Failed to send follower notifications for comic {comic_id}: {follower_notif_err}")
                    
        except Exception as notif_err:
            logger.error(f"Failed to send notification for comic {comic_id}: {notif_err}")

        logger.info(f"Comic {comic_id} rendering completed successfully!")
        
    except Exception as e:
        logger.exception(f"Rendering failed for comic {comic_id}: {e}")
        # Re-query fresh object to avoid detach issues
        if thread_db:
            try:
                thread_db.rollback()
                comic_record = thread_db.query(Comic).filter(Comic.id == comic_id).first()
                if comic_record:
                    comic_record.draft_job_status = "FAILED"
                    thread_db.commit()
            except Exception as dberr:
                logger.error(f"Failed to update RENDER_FAILED status: {dberr}")
    finally:
        if thread_db:
            thread_db.close()
