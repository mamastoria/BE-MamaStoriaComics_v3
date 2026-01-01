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
    status: Optional[str] = Field("pending", description="Withdrawal status")
    
    # Bank Details
    bank_name: Optional[str] = Field(None, description="Bank Name")
    account_number: Optional[str] = Field(None, description="Account Number")
    account_name: Optional[str] = Field(None, description="Account Name")


# ============ Response Schemas ============

class WithdrawalBase(BaseModel):
    """Base withdrawal schema"""
    id: int
    id_user: int
    amount: int
    status: str
    bank_name: Optional[str]
    account_number: Optional[str]
    account_name: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ORMConfig


class WithdrawalResponse(WithdrawalBase):
    """Full withdrawal response schema"""
    pass