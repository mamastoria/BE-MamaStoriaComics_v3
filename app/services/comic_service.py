"""
Comic Service
Business logic for comic creation, management, and publishing
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, cast
from sqlalchemy.dialects.postgresql import JSONB
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.comic import Comic
from app.models.user import User
from app.models.master_data import Style, Genre, Character, Background


class ComicService:
    """Service for comic operations"""
    
    @staticmethod
    def create_comic_from_story_idea(
        db: Session,
        user: User,
        story_idea: str,
        page_count: int,
        genre_ids: List[int],
        style_id: int
    ) -> Comic:
        """
        Create new comic from story idea (Step 1)
        
        Args:
            db: Database session
            user: User creating the comic
            story_idea: Story idea text
            page_count: Number of pages (1-25)
            genre_ids: List of genre IDs
            style_id: Style ID
            
        Returns:
            Created Comic object
        """
        # Validate genres
        genres = db.query(Genre).filter(Genre.id.in_(genre_ids)).all()
        if len(genres) != len(genre_ids):
            raise ValueError("Invalid genre IDs")
        
        # Validate style
        style = db.query(Style).filter(Style.id == style_id).first()
        if not style:
            raise ValueError("Invalid style ID")
        
        # Create comic
        comic = Comic(
            user_id=user.id_users,
            story_idea=story_idea,
            page_count=page_count,
            genre=[genre.name for genre in genres],  # Store as array of names
            style=style.name,
            draft_job_status="PENDING"
        )
        
        db.add(comic)
        db.commit()
        db.refresh(comic)
        
        # TODO: Trigger AI to generate summary, metadata, etc.
        # For now, just return the comic
        
        return comic
    
    @staticmethod
    def update_comic_summary(
        db: Session,
        comic: Comic,
        summary: str
    ) -> Comic:
        """
        Update comic summary
        
        Args:
            db: Database session
            comic: Comic object
            summary: New summary text
            
        Returns:
            Updated Comic object
        """
        comic.summary = summary
        db.commit()
        db.refresh(comic)
        return comic
    
    @staticmethod
    def update_comic_character(
        db: Session,
        comic: Comic,
        character_key: str
    ) -> Comic:
        """
        Update comic character selection (Step 2)
        
        Args:
            db: Database session
            comic: Comic object
            character_key: Selected character key/ID
            
        Returns:
            Updated Comic object
        """
        # TODO: Validate character exists
        comic.selected_character_key = character_key
        db.commit()
        db.refresh(comic)
        return comic
    
    @staticmethod
    def update_comic_backgrounds(
        db: Session,
        comic: Comic,
        background_ids: List[int]
    ) -> Comic:
        """
        Update comic background selection (Step 3)
        
        Args:
            db: Database session
            comic: Comic object
            background_ids: List of background IDs
            
        Returns:
            Updated Comic object
        """
        # Validate backgrounds
        backgrounds = db.query(Background).filter(Background.id.in_(background_ids)).all()
        if len(backgrounds) != len(background_ids):
            raise ValueError("Invalid background IDs")
        
        comic.selected_backgrounds = background_ids
        db.commit()
        db.refresh(comic)
        return comic
    
    @staticmethod
    def publish_comic(
        db: Session,
        comic: Comic,
        title: Optional[str] = None,
        synopsis: Optional[str] = None
    ) -> Comic:
        """
        Publish comic (make it public)
        
        Args:
            db: Database session
            comic: Comic object
            title: Optional custom title
            synopsis: Optional custom synopsis
            
        Returns:
            Published Comic object
        """
        # Update title and synopsis if provided
        if title:
            comic.title = title
        if synopsis:
            comic.synopsis = synopsis
        
        # Set publisher to creator's name if not already set
        if not comic.publisher and comic.user:
            comic.publisher = comic.user.full_name or comic.user.username
        
        # TODO: Validate comic is ready to publish (has panels, cover, etc.)
        
        db.commit()
        db.refresh(comic)
        return comic
    
    @staticmethod
    def track_comic_read(
        db: Session,
        comic: Comic,
        user: Optional[User] = None
    ) -> None:
        """
        Track comic read/view
        
        Args:
            db: Database session
            comic: Comic object
            user: Optional user who read the comic
        """
        # Increment view count
        comic.total_views += 1
        
        # Add to user's read history if user is logged in
        if user:
            from app.models.comic import ComicView
            
            # Check if already viewed
            existing = db.query(ComicView).filter(
                ComicView.comic_id == comic.id,
                ComicView.user_id == user.id_users
            ).first()
            
            if existing:
                # Update timestamp
                existing.updated_at = datetime.utcnow()
            else:
                # Create new view record
                view = ComicView(
                    comic_id=comic.id,
                    user_id=user.id_users
                )
                db.add(view)
        
        db.commit()
    
    @staticmethod
    def get_similar_comics(
        db: Session,
        comic: Comic,
        limit: int = 10
    ) -> List[Comic]:
        """
        Get similar comics based on genre and style
        
        Args:
            db: Database session
            comic: Reference comic
            limit: Number of similar comics to return
            
        Returns:
            List of similar Comic objects
        """
        # Base query for published comics excluding current one
        query = db.query(Comic).filter(
            Comic.id != comic.id,
            Comic.title.isnot(None),  # Only published comics
            Comic.cover_url.isnot(None)
        )
        
        criteria = []
        
        # 1. Match style
        if comic.style:
            criteria.append(Comic.style == comic.style)
            
        # 2. Overlapping genres (Any genre match)
        # Note: genre is a JSON array of strings
        if comic.genre and isinstance(comic.genre, list):
            # Using cast to JSONB ensures @> operator works on Postgres
            # We match if target comic contains ANY of the source comic's genres
            for g in comic.genre:
                criteria.append(cast(Comic.genre, JSONB).contains([g]))
        
        # If no criteria (no style, no genre), return empty or fallback?
        # Returning empty to avoid full table scan matches
        if not criteria:
            return []
            
        similar = query.filter(or_(*criteria)).order_by(
            Comic.total_views.desc()
        ).limit(limit).all()
        
        return similar
    
    @staticmethod
    def delete_comic(
        db: Session,
        comic: Comic
    ) -> None:
        """
        Delete comic and all related data
        
        Args:
            db: Database session
            comic: Comic object to delete
        """
        db.delete(comic)
        db.commit()
