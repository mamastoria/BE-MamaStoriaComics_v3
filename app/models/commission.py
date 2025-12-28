"""
Commission model - SQLAlchemy ORM
"""
from sqlalchemy import Column, BigInteger, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Commission(Base):
    """Commission model for tracking user commissions"""

    __tablename__ = "commissions"

    # Primary Key
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign Key to User
    id_user = Column(BigInteger, ForeignKey("users.id_users"), nullable=False)

    # Commission details
    kredit = Column(Integer, nullable=True)
    keterangan = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="commissions")

    def __repr__(self):
        return f"<Commission(id={self.id}, id_user={self.id_user}, kredit={self.kredit})>"