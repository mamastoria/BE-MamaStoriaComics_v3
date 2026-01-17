#!/usr/bin/env python3
"""Check status of failed comics"""
import sys
sys.path.insert(0, '.')
from app.core.database import get_session_local
from app.models.comic import Comic

SessionLocal = get_session_local()
db = SessionLocal()
for comic_id in [244, 245]:
    comic = db.query(Comic).filter(Comic.id == comic_id).first()
    if comic:
        print(f"\n=== Comic #{comic_id} ===")
        print(f"Status: {comic.draft_job_status}")
        print(f"Title: {comic.title}")
        print(f"Error: {comic.last_error_message}")
        print(f"Locked by: {comic.locked_by}")
        print(f"Locked at: {comic.locked_at}")
        print(f"Retry counts - script: {comic.script_retry_count}, image: {comic.image_retry_count}, video: {comic.video_retry_count}")
    else:
        print(f"\nComic #{comic_id} not found")
db.close()
