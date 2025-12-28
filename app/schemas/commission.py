"""
Commission Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.schemas.common import ORMConfig


# ============ Request Schemas ============

class CommissionCreate(BaseModel):
    """Schema for creating a commission"""
    id_user: int = Field(..., description="User ID")
    kredit: Optional[int] = Field(None, description="Commission credit amount")
    keterangan: Optional[str] = Field(None, description="Commission description")


# ============ Response Schemas ============

class CommissionBase(BaseModel):
    """Base commission schema"""
    id: int
    id_user: int
    kredit: Optional[int]
    keterangan: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ORMConfig


class CommissionResponse(CommissionBase):
    """Full commission response schema"""
    pass