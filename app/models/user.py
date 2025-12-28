"""
User model - SQLAlchemy ORM
Converted from Laravel User model
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    """User model for authentication and profile management"""
    
    __tablename__ = "users"
    
    # Primary Key
    id_users = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Basic Info
    full_name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone_number = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)
    
    # Referral System
    referral_code_id = Column(String, unique=True, nullable=False, index=True)
    referrals_for = Column(String, nullable=True)  # Code of referrer
    
    # Verification
    verification_code = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    last_verification_sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional Data
    region = Column(String, nullable=True)
    city = Column(String, nullable=True)
    timezone = Column(String, default='Asia/Jakarta', nullable=False)
    role = Column(String, default='creator', nullable=False)
    login_method = Column(String, default='mobile', nullable=False)
    external_id = Column(String, nullable=True)  # For Google OAuth
    
    # Credits & Balance
    kredit = Column(BigInteger, default=0, nullable=False)
    balance = Column(BigInteger, default=0, nullable=False)
    
    # Profile
    profile_photo_path = Column(String, nullable=True)
    
    # Subscription
    publish_quota = Column(Integer, default=0, nullable=False)
    
    # Rating System
    previous_rating = Column(Integer, nullable=True)
    previous_rating_name = Column(String, nullable=True)
    
    # FCM Token for notifications
    fcm_token = Column(Text, nullable=True)
    
    # Remember Token (for sessions)
    remember_token = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    comics = relationship("Comic", back_populates="user", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    
    # Many-to-Many relationships
    liked_comics = relationship(
        "Comic",
        secondary="comic_user",
        back_populates="liked_by_users"
    )
    
    read_comics = relationship(
        "Comic",
        secondary="comic_views",
        back_populates="viewed_by_users"
    )
    
    def __repr__(self):
        return f"<User(id={self.id_users}, username={self.username}, email={self.email})>"
    
    @property
    def is_active(self) -> bool:
        """Check if user is active (verified)"""
        return self.is_verified
    
    @property
    def has_active_subscription(self) -> bool:
        """Check if user has active subscription"""
        # This will be implemented when we add subscription logic
        return False
