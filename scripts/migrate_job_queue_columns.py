"""
Database Migration: Add Job Queue Columns

Run this script to add the new columns for the database-driven job queue system.

Usage:
    python scripts/migrate_job_queue_columns.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

def run_migration():
    """Add job queue columns to comics table"""
    
    print("=" * 60)
    print("JOB QUEUE MIGRATION")
    print("=" * 60)
    
    # Get database connection
    from app.core.database import get_engine
    from sqlalchemy import text
    
    engine = get_engine()
    
    # Columns to add
    columns = [
        # Retry tracking
        ("script_retry_count", "INTEGER DEFAULT 0 NOT NULL"),
        ("image_retry_count", "INTEGER DEFAULT 0 NOT NULL"),
        ("video_retry_count", "INTEGER DEFAULT 0 NOT NULL"),
        ("last_error_message", "TEXT"),
        ("last_error_at", "TIMESTAMP WITH TIME ZONE"),
        
        # Locking
        ("locked_by", "VARCHAR(100)"),
        ("locked_at", "TIMESTAMP WITH TIME ZONE"),
        
        # Timing (if not already exists)
        ("script_started_at", "TIMESTAMP WITH TIME ZONE"),
        ("script_completed_at", "TIMESTAMP WITH TIME ZONE"),
        ("render_started_at", "TIMESTAMP WITH TIME ZONE"),
        ("render_completed_at", "TIMESTAMP WITH TIME ZONE"),
        ("clipping_started_at", "TIMESTAMP WITH TIME ZONE"),
        ("clipping_completed_at", "TIMESTAMP WITH TIME ZONE"),
        ("video_started_at", "TIMESTAMP WITH TIME ZONE"),
        ("video_completed_at", "TIMESTAMP WITH TIME ZONE"),
    ]
    
    with engine.connect() as conn:
        for col_name, col_type in columns:
            try:
                sql = f"ALTER TABLE comics ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                conn.execute(text(sql))
                print(f"✓ Added column: {col_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"- Column exists: {col_name}")
                else:
                    print(f"✗ Error adding {col_name}: {e}")
        
        # Commit changes
        try:
            conn.commit()
        except Exception:
            pass  # Some configs auto-commit
    
    print("=" * 60)
    print("Migration completed!")
    print("=" * 60)


if __name__ == "__main__":
    run_migration()
