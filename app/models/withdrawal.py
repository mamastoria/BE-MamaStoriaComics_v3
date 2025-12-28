"""
Withdrawal model - SQLAlchemy ORM
"""
from sqlalchemy import Column, BigInteger, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Withdrawal(Base):
    """Withdrawal model for tracking user withdrawals"""

    __tablename__ = "withdrawals"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Key to User
    id_user = Column(Integer, nullable=False)

    # Withdrawal details
    amount = Column(BigInteger, nullable=False)
    status = Column(String(255), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<Withdrawal(id={self.id}, id_user={self.id_user}, amount={self.amount}, status={self.status})>"