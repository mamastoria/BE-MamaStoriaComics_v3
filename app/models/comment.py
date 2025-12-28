"""
Comment model for comic reviews
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Comment(Base):
    """Comment model for comic reviews and feedback"""
    
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    comic_id = Column(Integer, ForeignKey('comics.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id_users', ondelete='CASCADE'), nullable=False, index=True)
    
    content = Column(Text, nullable=False)
    rating = Column(Integer, nullable=True)  # 1-5 stars
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    comic = relationship("Comic", back_populates="comments")
    user = relationship("User", back_populates="comments")
    
    def __repr__(self):
        return f"<Comment(id={self.id}, comic_id={self.comic_id}, user_id={self.user_id})>"
