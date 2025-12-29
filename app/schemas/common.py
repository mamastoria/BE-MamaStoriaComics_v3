"""
Common/Shared Pydantic schemas
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any
from datetime import datetime


class ResponseBase(BaseModel):
    """Base response schema"""
    ok: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response schema"""
    ok: bool = False
    error: str
    detail: Optional[str] = None


class PaginationMeta(BaseModel):
    """Pagination metadata"""
    current_page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel):
    """Paginated response schema"""
    ok: bool = True
    data: List[Any]
    meta: PaginationMeta


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int  # seconds


class MessageResponse(ResponseBase):
    """Simple message response"""
    pass


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""
    refresh_token: str = Field(..., description="Refresh token to generate new access token")


# Config for all schemas
ORMConfig = ConfigDict(from_attributes=True)
