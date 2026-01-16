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

        # Map DB style/genre names to core style/nuance IDs
        try:
            import core
        except Exception:
            core = None
        
        # Create comic
        # Store core-mapped style/nuance IDs when possible for consistent generation
        style_key = str(style_id)
        genre_keys = [str(genre.id) for genre in genres]
        if core is not None:
            style_key = core.map_style_id(style_id, style.name)
            genre_keys = core.map_nuance_ids(
                nuance_ids=[str(genre.id) for genre in genres],
                nuance_names=[genre.name for genre in genres],
            )

        comic = Comic(
            user_id=user.id_users,
            story_idea=story_idea,
            page_count=page_count,
            genre=genre_keys,  # Store as array of ID strings
            style=str(style_key),  # Store style ID as string for core.COMIC_STYLES matching
            draft_job_status="PENDING",
            publisher=user.full_name or user.username
        )
        
        # DEBUG: Log style and genre being saved
        from app.core.logging_config import logger
        logger.info(f"💾 Creating comic with style={style_key} (from {style.name}), genres={genre_keys} (from {[g.name for g in genres]})")
        
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

        # Mark comic as published/active
        comic.status = True
        
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
    def track_comic_share(
        db: Session,
        comic: Comic,
        user: Optional[User] = None
    ) -> int:
        """
        Track comic share
        
        Args:
            db: Database session
            comic: Comic object
            user: Optional user who shared the comic
            
        Returns:
            New total share count
        """
        # Increment share count
        comic.total_shares += 1
        
        # Add to share history if user is logged in
        if user:
            from app.models.comic import ComicShare
            
            # Check if already shared (optional: only allow 1 share count per user? 
            # or allow multiple shares? Request implies insert/update total share.
            # Usually shares are multiple times per user allowed on different platforms, 
            # but tracking table implies unique record per (user, comic)?
            # Let's assume we log every share action or unique?
            # User said "mirip seperti comic_views". Comic views updates timestamp if exists. 
            # I'll follow that pattern.
            
            existing = db.query(ComicShare).filter(
                ComicShare.comic_id == comic.id,
                ComicShare.user_id == user.id_users
            ).first()
            
            if existing:
                # Update timestamp
                existing.updated_at = datetime.utcnow()
            else:
                # Create new share record
                share = ComicShare(
                    comic_id=comic.id,
                    user_id=user.id_users
                )
                db.add(share)
        
        db.commit()
        db.refresh(comic)
        return comic.total_shares
    
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
            Comic.status == True,  # Only active comics
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
            Comic.created_at.desc()
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
