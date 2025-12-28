"""
Notification and Banner models
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Notification(Base):
    """Notification model for user notifications"""
    
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id_users', ondelete='CASCADE'), nullable=False, index=True)
    
    type = Column(String, nullable=False)  # comment, like, milestone, etc.
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    data = Column(Text, nullable=True)  # JSON data
    
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.type})>"
    
    @property
    def is_read(self) -> bool:
        """Check if notification has been read"""
        return self.read_at is not None


class Banner(Base):
    """Banner model for app banners/promotions"""
    
    __tablename__ = "banners"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    title = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    image_url = Column(String, nullable=False)
    link_url = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    comics = relationship(
        "Comic",
        secondary="banner_comic",
        back_populates="banners"
    )
    
    def __repr__(self):
        return f"<Banner(id={self.id}, title={self.title}, slug={self.slug})>"


# Pivot table for Banner-Comic relationship
class BannerComic(Base):
    """Pivot table for banner-comic relationship"""
    
    __tablename__ = "banner_comic"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    banner_id = Column(Integer, ForeignKey('banners.id', ondelete='CASCADE'), nullable=False, index=True)
    comic_id = Column(Integer, ForeignKey('comics.id', ondelete='CASCADE'), nullable=False, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
