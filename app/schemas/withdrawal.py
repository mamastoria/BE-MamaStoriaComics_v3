"""
Withdrawal Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.schemas.common import ORMConfig


# ============ Request Schemas ============

class WithdrawalCreate(BaseModel):
    """Schema for creating a withdrawal"""
    id_user: int = Field(..., description="User ID")
    amount: int = Field(..., gt=0, description="Withdrawal amount")
    status: str = Field(..., description="Withdrawal status")


# ============ Response Schemas ============

class WithdrawalBase(BaseModel):
    """Base withdrawal schema"""
    id: int
    id_user: int
    amount: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ORMConfig


class WithdrawalResponse(WithdrawalBase):
    """Full withdrawal response schema"""
    pass