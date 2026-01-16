#!/usr/bin/env python3
"""
Fix stuck comics by clearing locks and resetting status
"""
import sys
sys.path.insert(0, '.')
from app.core.database import get_session_local
from app.models.comic import Comic
from datetime import datetime

SessionLocal = get_session_local()
db = SessionLocal()

try:
    for comic_id in [244, 245]:
        comic = db.query(Comic).filter(Comic.id == comic_id).first()
        if comic:
            print(f"\n=== Comic #{comic_id} ===")
            print(f"Before - Status: {comic.draft_job_status}, Locked by: {comic.locked_by}")
            
            # Reset status and clear locks
            if comic.draft_job_status in ["PROCESSING", "RENDERING"]:
                comic.draft_job_status = "SCRIPT_READY"  # Ready for image generation
            
            comic.locked_by = None
            comic.locked_at = None
            comic.last_error_message = f"Recovered from stuck status on {datetime.now()}"
            comic.last_error_at = datetime.now()
            
            db.commit()
            print(f"After  - Status: {comic.draft_job_status}, Locked by: {comic.locked_by}")
            print(f"✅ Comic #{comic_id} fixed!")
        else:
            print(f"\n❌ Comic #{comic_id} not found")
finally:
    db.close()
    print("\n✅ Done!")
