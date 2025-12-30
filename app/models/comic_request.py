"""
Comic Request model - SQLAlchemy ORM
"""
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class ComicRequest(Base):
    """Model for physical comic souvenir requests"""
    
    __tablename__ = "comic_requests"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id_users", ondelete="CASCADE"), nullable=False, index=True)
    
    recipient_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    shipping_address = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String, default="PENDING", nullable=False)
    
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", backref="comic_requests")
    
    def __repr__(self):
        return f"<ComicRequest(id={self.id}, user_id={self.user_id}, status={self.status})>"
