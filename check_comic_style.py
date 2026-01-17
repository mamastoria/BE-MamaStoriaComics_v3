"""
Quick check: Are style and genre being saved to comic records?
"""
import sys
from pathlib import Path

# Add project root to Python path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal
from app.models.comic import Comic

db = SessionLocal()

print("\n=== LATEST 5 COMICS - STYLE & GENRE CHECK ===\n")

comics = db.query(Comic).order_by(Comic.id.desc()).limit(5).all()

if not comics:
    print("No comics found in database")
else:
    for c in comics:
        print(f"Comic #{c.id}:")
        print(f"  Title: {c.title or '(no title)'}")
        print(f"  Style: {c.style} (type: {type(c.style).__name__})")
        print(f"  Genre: {c.genre} (type: {type(c.genre).__name__})")
        print(f"  Status: {c.draft_job_status}")
        print(f"  Created: {c.created_at}")
        print()

db.close()
