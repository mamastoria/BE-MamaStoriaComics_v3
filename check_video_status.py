"""
Check Video Generation Status
Shows how many videos are currently processing, pending, and completed
"""
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import get_session_local
from app.models.comic import Comic
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta

def check_video_status():
    """Check current video generation status"""
    SessionLocal = get_session_local()
    db = SessionLocal()
    
    try:
        print("\n" + "="*60)
        print("VIDEO GENERATION STATUS")
        print("="*60 + "\n")
        
        # 1. Videos currently processing (locked and working)
        lock_timeout = 30  # minutes
        lock_expiry = datetime.now() - timedelta(minutes=lock_timeout)
        
        processing = db.query(Comic).filter(
            and_(
                Comic.draft_job_status == 'PROCESSING',
                Comic.preview_video_url.is_(None),
                Comic.locked_by.isnot(None),
                Comic.locked_at >= lock_expiry
            )
        ).all()
        
        print(f"🎬 ACTIVELY PROCESSING: {len(processing)} video(s)")
        for comic in processing:
            elapsed = (datetime.now() - comic.video_started_at).total_seconds() / 60 if comic.video_started_at else 0
            print(f"   - Comic #{comic.id}: '{comic.title}' ({elapsed:.1f} min)")
            print(f"     Worker: {comic.locked_by}")
            print(f"     Started: {comic.video_started_at}")
        
        # 2. Videos pending (waiting in queue)
        pending = db.query(Comic).filter(
            and_(
                Comic.draft_job_status == 'PROCESSING',
                Comic.cover_url.isnot(None),
                Comic.preview_video_url.is_(None),
                or_(
                    Comic.locked_by.is_(None),
                    Comic.locked_at < lock_expiry
                )
            )
        ).all()
        
        print(f"\n⏳ PENDING (In Queue): {len(pending)} video(s)")
        for comic in pending:
            print(f"   - Comic #{comic.id}: '{comic.title}'")
            if comic.video_started_at:
                elapsed = (datetime.now() - comic.video_started_at).total_seconds() / 60
                print(f"     Last attempt: {elapsed:.1f} min ago (retry: {comic.video_retry_count or 0})")
        
        # 3. Videos completed (has URL)
        completed = db.query(Comic).filter(
            Comic.preview_video_url.isnot(None)
        ).count()
        
        print(f"\n✅ COMPLETED: {completed} video(s)")
        
        # 4. Comics with images but no video attempt yet
        ready_for_video = db.query(Comic).filter(
            and_(
                Comic.cover_url.isnot(None),
                Comic.preview_video_url.is_(None),
                Comic.draft_job_status != 'PROCESSING'
            )
        ).count()
        
        print(f"\n📸 IMAGES READY (No video yet): {ready_for_video} comic(s)")
        
        # 5. Failed/stuck videos
        stuck = db.query(Comic).filter(
            and_(
                Comic.draft_job_status == 'PROCESSING',
                Comic.preview_video_url.is_(None),
                Comic.video_retry_count > 2
            )
        ).all()
        
        print(f"\n❌ FAILED/STUCK: {len(stuck)} video(s)")
        for comic in stuck:
            print(f"   - Comic #{comic.id}: '{comic.title}' (retries: {comic.video_retry_count})")
        
        # Summary
        total_need_video = len(processing) + len(pending) + ready_for_video
        print(f"\n" + "="*60)
        print(f"SUMMARY:")
        print(f"  - Active: {len(processing)}")
        print(f"  - Queued: {len(pending)}")
        print(f"  - Ready: {ready_for_video}")
        print(f"  - Total need video: {total_need_video}")
        print(f"  - Completed: {completed}")
        print(f"  - Failed: {len(stuck)}")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    check_video_status()
