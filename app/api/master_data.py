"""
Master Data API endpoints
Endpoints for styles, genres, characters, backgrounds
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.master_data import Style, Genre, Character, Background
from app.schemas.comic import (
    StyleResponse,
    GenreResponse,
    CharacterResponse,
    BackgroundResponse
)

router = APIRouter()


@router.get("/styles", response_model=dict)
async def get_styles(db: Session = Depends(get_db)):
    """
    Get all available comic styles
    
    Returns list of styles with id, name, description, and image_url
    """
    styles = db.query(Style).all()
    
    return {
        "ok": True,
        "data": [StyleResponse.model_validate(style).model_dump() for style in styles]
    }


@router.get("/genres", response_model=dict)
async def get_genres(db: Session = Depends(get_db)):
    """
    Get all available comic genres
    
    Returns list of genres with id, name, and description
    """
    genres = db.query(Genre).all()
    
    return {
        "ok": True,
        "data": [GenreResponse.model_validate(genre).model_dump() for genre in genres]
    }


@router.get("/characters", response_model=dict)
async def get_characters(db: Session = Depends(get_db)):
    """
    Get all available character templates
    
    Returns list of characters with id, name, image_url, and description
    """
    characters = db.query(Character).all()
    
    return {
        "ok": True,
        "data": [CharacterResponse.model_validate(char).model_dump() for char in characters]
    }


@router.get("/backgrounds", response_model=dict)
async def get_backgrounds(db: Session = Depends(get_db)):
    """
    Get all available background templates
    
    Returns list of backgrounds with id, name, image_url, and description
    """
    backgrounds = db.query(Background).all()
    
    return {
        "ok": True,
        "data": [BackgroundResponse.model_validate(bg).model_dump() for bg in backgrounds]
    }


# Shorter aliases (for backward compatibility with Laravel routes)
@router.get("/chars", response_model=dict)
async def get_chars(db: Session = Depends(get_db)):
    """Alias for /characters"""
    return await get_characters(db)


@router.get("/bg", response_model=dict)
async def get_bg(db: Session = Depends(get_db)):
    """Alias for /backgrounds"""
    return await get_backgrounds(db)
