"""
Comic model - SQLAlchemy ORM
Converted from Laravel Comic model
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Comic(Base):
    """Comic model for comic content and metadata"""
    
    __tablename__ = "comics"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Key
    user_id = Column(Integer, ForeignKey('users.id_users', ondelete='CASCADE'), nullable=False, index=True)
    
    # Stage 1: Story Idea Data
    story_idea = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    theme = Column(String, nullable=True)
    keywords = Column(JSON, nullable=True)  # Array of keywords
    
    # Stage 2: Style Data
    style = Column(String, nullable=True)
    mood = Column(String, nullable=True)
    page_count = Column(Integer, nullable=True)
    
    # Stage 3: Character & Background Selection
    selected_character_key = Column(String, nullable=True)
    selected_backgrounds = Column(JSON, nullable=True)  # Array of background IDs
    
    # Final Stage: Publish Data
    title = Column(String, nullable=True, index=True)
    publisher = Column(String, nullable=True, index=True)
    genre = Column(JSON, nullable=True)  # Array of genres
    synopsis = Column(Text, nullable=True)
    tags = Column(String, nullable=True, index=True)  # e.g., "#sultanagung #kerajaan"
    
    # URLs (after render/publish)
    cover_url = Column(String, nullable=True)
    preview_video_url = Column(String, nullable=True)
    pdf_url = Column(String, nullable=True)
    narration_audio_url = Column(String, nullable=True)
    
    # Draft Job Status (for async processing)
    draft_job_id = Column(String, nullable=True)
    draft_job_status = Column(String, nullable=True)  # QUEUED, PROCESSING, COMPLETED, FAILED
    
    # Layout
    layout = Column(String, nullable=True)  # e.g., "portrait", "landscape"
    
    # Statistics
    total_views = Column(BigInteger, default=0, nullable=False)
    total_likes = Column(BigInteger, default=0, nullable=False)
    total_comments = Column(BigInteger, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="comics")
    panels = relationship("ComicPanel", back_populates="comic", cascade="all, delete-orphan", order_by="ComicPanel.page_number, ComicPanel.panel_number")
    comments = relationship("Comment", back_populates="comic", cascade="all, delete-orphan")
    panel_ideas = relationship("ComicPanelIdea", back_populates="comic", cascade="all, delete-orphan")
    
    # Many-to-Many relationships
    liked_by_users = relationship(
        "User",
        secondary="comic_user",
        back_populates="liked_comics"
    )
    
    viewed_by_users = relationship(
        "User",
        secondary="comic_views",
        back_populates="read_comics"
    )
    
    banners = relationship(
        "Banner",
        secondary="banner_comic",
        back_populates="comics"
    )
    
    def __repr__(self):
        return f"<Comic(id={self.id}, title={self.title}, user_id={self.user_id})>"
    
    @property
    def is_published(self) -> bool:
        """Check if comic is published (has title and cover)"""
        return bool(self.title and self.cover_url)
    
    @property
    def is_draft(self) -> bool:
        """Check if comic is still in draft"""
        return not self.is_published


# Pivot table for Comic-User likes (Many-to-Many)
class ComicUser(Base):
    """Pivot table for comic likes"""
    
    __tablename__ = "comic_user"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    comic_id = Column(Integer, ForeignKey('comics.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id_users', ondelete='CASCADE'), nullable=False, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# Pivot table for Comic Views (Read History)
class ComicView(Base):
    """Pivot table for comic read history"""
    
    __tablename__ = "comic_views"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    comic_id = Column(Integer, ForeignKey('comics.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id_users', ondelete='CASCADE'), nullable=False, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
