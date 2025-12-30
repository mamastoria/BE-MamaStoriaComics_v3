import sys
import os
import asyncio
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pathlib import Path

# Add parent directory to path to import app modules
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))

from app.core.config import settings
from app.models.master_data import Style, Genre
from app.services.google_storage_service import GoogleStorageService

# ==========================================
# CONFIGURATION
# ==========================================
# Ganti dengan Connection String Database Sumber (mamastoria101)
# Contoh: postgresql://user:pass@IP:PORT/db_name
SOURCE_DATABASE_URL = input("Masukkan Connection String Database Sumber (mamastoria101): ")

# Destination Database (diambil dari .env project ini)
DEST_DATABASE_URL = settings.DATABASE_URL

# ==========================================
# SETUP
# ==========================================

async def download_image(url):
    """Download image from URL"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            if response.status_code == 200:
                return response.content, response.headers.get("content-type")
            else:
                print(f"Failed to download image: {url} (Status: {response.status_code})")
                return None, None
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None, None

async def migrate_data():
    print(f"Connecting to Source: {SOURCE_DATABASE_URL}")
    source_engine = create_engine(SOURCE_DATABASE_URL)
    SourceSession = sessionmaker(bind=source_engine)
    source_db = SourceSession()

    print(f"Connecting to Destination: {DEST_DATABASE_URL}")
    dest_engine = create_engine(DEST_DATABASE_URL)
    DestSession = sessionmaker(bind=dest_engine)
    dest_db = DestSession()

    # ==========================
    # MIGRATE GENRES
    # ==========================
    print("\n--- Migrating Genres ---")
    try:
        # Read raw sql from source if models match, or just use text query
        # Assuming table name is "genres" in source
        genres = source_db.execute(text("SELECT id, name, description FROM public.genres")).fetchall()
        
        for g in genres:
            # Check if exists
            existing = dest_db.query(Genre).filter(Genre.name == g.name).first()
            if existing:
                print(f"Genre '{g.name}' already exists. Skipping.")
                continue
            
            new_genre = Genre(
                name=g.name,
                description=g.description
            )
            dest_db.add(new_genre)
            print(f"Added Genre: {g.name}")
        
        dest_db.commit()
    except Exception as e:
        print(f"Error migrating genres: {e}")
        dest_db.rollback()

    # ==========================
    # MIGRATE STYLES + IMAGES
    # ==========================
    print("\n--- Migrating Styles ---")
    try:
        # Assuming table styles has image_url
        styles = source_db.execute(text("SELECT id, name, description, image_url, prompt_modifier FROM public.styles")).fetchall()
        
        for s in styles:
            existing = dest_db.query(Style).filter(Style.name == s.name).first()
            if existing:
                print(f"Style '{s.name}' already exists. Skipping.")
                continue
            
            new_image_url = s.image_url
            
            # Process Image if exists
            if s.image_url:
                print(f"Downloading image for '{s.name}' from {s.image_url}...")
                image_data, content_type = await download_image(s.image_url)
                
                if image_data:
                    # Upload to Destination GCS
                    filename = f"styles/{s.name.lower().replace(' ', '_')}_{os.urandom(4).hex()}.jpg" # Normalize filename
                    print(f"Uploading to {settings.GOOGLE_BUCKET_NAME}/{filename}...")
                    
                    try:
                        # Assuming GoogleStorageService has upload method, we might need to use basic storage client or modify service
                        # GoogleStorageService usually requires file-like object. 
                        # We'll use the service's underlying client if possible or just implement upload here.
                        
                        # Let's check GoogleStorageService in app code. 
                        # It has `upload_file` which takes `UploadFile` (FastAPI). 
                        # We just have bytes. We need to implement direct upload.
                        
                        from google.cloud import storage
                        storage_client = storage.Client(project=settings.GOOGLE_PROJECT_ID)
                        bucket = storage_client.bucket(settings.GOOGLE_BUCKET_NAME)
                        blob = bucket.blob(filename)
                        blob.upload_from_string(image_data, content_type=content_type or 'image/jpeg')
                        
                        # Make public or signed? Assuming public readable for app
                        # blob.make_public() # Optional depending on bucket config
                        
                        new_image_url = f"https://storage.googleapis.com/{settings.GOOGLE_BUCKET_NAME}/{filename}"
                        print(f"Uploaded. New URL: {new_image_url}")
                        
                    except Exception as upload_err:
                        print(f"Failed to upload image: {upload_err}")
                else:
                    print("Skipping image upload (download failed). Keeping original URL.")

            new_style = Style(
                name=s.name,
                description=s.description,
                image_url=new_image_url,
                prompt_modifier=s.prompt_modifier
            )
            dest_db.add(new_style)
            print(f"Added Style: {s.name}")

        dest_db.commit()

    except Exception as e:
        print(f"Error migrating styles: {e}")
        dest_db.rollback()

    print("\nMigration Completed.")

if __name__ == "__main__":
    if not SOURCE_DATABASE_URL:
        print("Error: Source Database URL connection string is required.")
        sys.exit(1)
        
    asyncio.run(migrate_data())
