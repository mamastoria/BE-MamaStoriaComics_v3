"""
Comic Panel and Panel Idea models
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class ComicPanel(Base):
    """Comic panel model - represents individual pages/panels of a comic"""
    
    __tablename__ = "comic_panels"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    comic_id = Column(Integer, ForeignKey('comics.id', ondelete='CASCADE'), nullable=False, index=True)
    
    page_number = Column(Integer, nullable=False, index=True)
    panel_number = Column(Integer, nullable=False)
    
    # Panel content
    image_url = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    
    # Script data (from AI generation)
    page_description = Column(Text, nullable=True)
    page_narration = Column(Text, nullable=True)
    dialogues = Column(JSON, nullable=True)  # Array of dialogue objects
    main_characters_on_page = Column(JSON, nullable=True)  # Array of character names
    
    # Visual instructions
    instruksi_visual = Column(JSON, nullable=True)
    instruksi_render_teks = Column(JSON, nullable=True)
    
    # Audio
    narration = Column(Text, nullable=True)
    narration_audio_url = Column(String, nullable=True)
    audio_duration = Column(Integer, nullable=True)  # in seconds
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    comic = relationship("Comic", back_populates="panels")
    
    def __repr__(self):
        return f"<ComicPanel(id={self.id}, comic_id={self.comic_id}, page={self.page_number})>"


class ComicPanelIdea(Base):
    """Comic panel idea model - for draft generation process"""
    
    __tablename__ = "comic_panel_ideas"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    comic_id = Column(Integer, ForeignKey('comics.id', ondelete='CASCADE'), nullable=False, index=True)
    
    page_number = Column(Integer, nullable=False)
    panel_number = Column(Integer, nullable=False)
    
    description = Column(Text, nullable=True)
    narration = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    comic = relationship("Comic", back_populates="panel_ideas")
    
    def __repr__(self):
        return f"<ComicPanelIdea(id={self.id}, comic_id={self.comic_id}, page={self.page_number})>"
