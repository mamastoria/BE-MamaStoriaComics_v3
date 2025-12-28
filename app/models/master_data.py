"""
Master data models: Style, Genre, Character, Background
"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class Style(Base):
    """Style model for comic visual styles"""
    
    __tablename__ = "styles"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    prompt_modifier = Column(Text, nullable=True)  # AI prompt modifier for this style
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Style(id={self.id}, name={self.name})>"


class Genre(Base):
    """Genre model for comic genres"""
    
    __tablename__ = "genres"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Genre(id={self.id}, name={self.name})>"


class Character(Base):
    """Character model for character templates"""
    
    __tablename__ = "characters"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, index=True)
    image_url = Column(String, nullable=True)
    description_prompt = Column(Text, nullable=True)  # AI description
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Character(id={self.id}, name={self.name})>"


class Background(Base):
    """Background model for background/location templates"""
    
    __tablename__ = "backgrounds"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, index=True)
    image_url = Column(String, nullable=True)
    description_prompt = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Background(id={self.id}, name={self.name})>"


class AssetMusic(Base):
    """Asset music model for background music"""
    
    __tablename__ = "asset_music"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, index=True)
    file_url = Column(String, nullable=False)
    duration = Column(Integer, nullable=True)  # in seconds
    genre = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<AssetMusic(id={self.id}, name={self.name})>"
