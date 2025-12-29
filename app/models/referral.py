"""
Referral model - SQLAlchemy ORM
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Referral(Base):
    """Referral model for tracking user referrals"""

    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Keys
    referrer_id = Column(Integer, ForeignKey('users.id_users'), nullable=False)
    referred_user_id = Column(Integer, ForeignKey('users.id_users'), nullable=False)

    # Referral code used
    referral_code = Column(String, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="referrals_made")
    referred_user = relationship("User", foreign_keys=[referred_user_id], back_populates="referrals_received")

    def __repr__(self):
        return f"<Referral(id={self.id}, referrer_id={self.referrer_id}, referred_user_id={self.referred_user_id})>"