"""
Comic Request Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.schemas.common import ORMConfig


# ============ Request Schemas ============

class ComicRequestCreate(BaseModel):
    """Schema for creating a comic souvenir request"""
    recipient_name: str = Field(..., min_length=2, description="Nama penerima paket")
    phone_number: str = Field(..., min_length=8, description="Nomor telepon/WA aktif")
    shipping_address: str = Field(..., min_length=10, description="Alamat lengkap pengiriman")
    notes: Optional[str] = Field(None, description="Catatan tambahan (misal: Judul komik)")


# ============ Response Schemas ============

class ComicRequestResponse(BaseModel):
    """Schema for comic request response"""
    id: int
    user_id: int
    recipient_name: str
    phone_number: str
    shipping_address: str
    notes: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ORMConfig
