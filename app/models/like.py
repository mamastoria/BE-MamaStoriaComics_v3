"""
Like model for comic likes
"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


class Like(Base):
    """Model for comic likes"""
    __tablename__ = "likes"
    
    id = Column(Integer, primary_key=True, index=True)
    comic_id = Column(Integer, ForeignKey("comics.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id_users", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Unique constraint - user can only like a comic once
    __table_args__ = (
        UniqueConstraint('comic_id', 'user_id', name='unique_like'),
    )
    
    # Relationships - lazy loaded without back_populates to avoid circular issues
    comic = relationship("Comic", lazy="select")
    user = relationship("User", lazy="select")

