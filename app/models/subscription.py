"""
Subscription and Payment models
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger, Text, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class SubscriptionPackage(Base):
    """Subscription package model"""
    
    __tablename__ = "subscription_packages"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    price = Column(BigInteger, nullable=False)  # in cents/smallest currency unit
    duration_days = Column(Integer, nullable=False)
    publish_quota = Column(Integer, nullable=False)  # Number of comics can publish
    bonus_credits = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    subscriptions = relationship("Subscription", back_populates="package")
    
    def __repr__(self):
        return f"<SubscriptionPackage(id={self.id}, name={self.name}, price={self.price})>"


class Subscription(Base):
    """User subscription model"""
    
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id_users', ondelete='CASCADE'), nullable=False, index=True)
    package_id = Column(Integer, ForeignKey('subscription_packages.id'), nullable=False)
    
    status = Column(String, nullable=False, default='pending')  # pending, active, expired, cancelled
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    package = relationship("SubscriptionPackage", back_populates="subscriptions")
    
    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, status={self.status})>"
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active"""
        from datetime import datetime
        if self.status != 'active':
            return False
        if self.end_date and self.end_date < datetime.now():
            return False
        return True


class PaymentTransaction(Base):
    """Payment transaction model for DOKU payments"""
    
    __tablename__ = "payment_transactions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id_users', ondelete='CASCADE'), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=True)
    
    invoice_number = Column(String, unique=True, nullable=False, index=True)
    amount = Column(BigInteger, nullable=False)
    payment_method = Column(String, nullable=True)
    
    status = Column(String, nullable=False, default='pending')  # pending, success, failed, expired
    payment_url = Column(Text, nullable=True)
    
    # DOKU specific fields
    doku_order_id = Column(String, nullable=True, index=True)
    doku_response = Column(Text, nullable=True)  # JSON response from DOKU
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<PaymentTransaction(id={self.id}, invoice={self.invoice_number}, status={self.status})>"


class Transaction(Base):
    """General transaction model for wallet/earnings"""
    
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id_users', ondelete='CASCADE'), nullable=False, index=True)
    
    type = Column(String, nullable=False)  # credit, debit, referral_bonus, withdrawal
    amount = Column(BigInteger, nullable=False)
    description = Column(Text, nullable=True)
    reference_id = Column(String, nullable=True)  # Reference to related record
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, user_id={self.user_id}, type={self.type}, amount={self.amount})>"
