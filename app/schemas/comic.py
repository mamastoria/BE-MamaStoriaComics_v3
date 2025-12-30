"""
Comic Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from app.schemas.common import ORMConfig
from app.schemas.user import UserPublic


# ============ Request Schemas ============

class CreateStoryIdea(BaseModel):
    """Schema for creating comic story idea (Step 1)"""
    story_idea: str = Field(..., min_length=10, description="Story idea text or transcribed audio")
    page_count: int = Field(..., ge=1, le=25, description="Number of pages (1-25)")
    genre_ids: List[int] = Field(..., min_items=1, description="List of genre IDs")
    style_id: int = Field(..., description="Style ID")


class UpdateSummary(BaseModel):
    """Schema for updating comic summary"""
    summary: str = Field(..., min_length=50)


class UpdateCharacter(BaseModel):
    """Schema for updating comic character (Step 2)"""
    character_key: str = Field(..., description="Selected character key/ID")


class UpdateBackgrounds(BaseModel):
    """Schema for updating comic backgrounds (Step 3)"""
    background_ids: List[int] = Field(..., min_items=1, description="List of background IDs")


class GenerateDraft(BaseModel):
    """Schema for generating comic draft"""
    # Optional parameters for draft generation
    force_regenerate: bool = False


class PublishComic(BaseModel):
    """Schema for publishing comic"""
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    synopsis: Optional[str] = None


# ============ Response Schemas ============

class ComicBase(BaseModel):
    """Base comic schema"""
    id: int
    user_id: int
    title: Optional[str]
    cover_url: Optional[str]
    
    model_config = ORMConfig


class ComicListItem(ComicBase):
    """Comic list item schema (for listing)"""
    synopsis: Optional[str]
    tags: Optional[str]
    genre: Optional[List[str]]
    total_views: int
    total_likes: int
    total_comments: int
    created_at: datetime
    updated_at: datetime
    
    # Include creator info
    user: Optional[UserPublic] = None
    
    model_config = ORMConfig


class ComicDetail(ComicListItem):
    """Full comic detail schema"""
    story_idea: Optional[str]
    summary: Optional[str]
    theme: Optional[str]
    keywords: Optional[List[str]]
    style: Optional[str]
    mood: Optional[str]
    page_count: Optional[int]
    publisher: Optional[str]
    preview_video_url: Optional[str]
    pdf_url: Optional[str]
    narration_audio_url: Optional[str]
    selected_character_key: Optional[str]
    selected_backgrounds: Optional[List[Union[int, str]]]
    layout: Optional[str]
    
    model_config = ORMConfig


class DraftStatus(BaseModel):
    """Draft generation status response"""
    comic_id: int
    status: str  # QUEUED, PROCESSING, COMPLETED, FAILED
    progress: Optional[int] = None  # 0-100
    message: Optional[str] = None
    draft_job_id: Optional[str] = None


class ComicPanel(BaseModel):
    """Comic panel schema"""
    id: int
    comic_id: int
    page_number: int
    panel_number: int
    image_url: Optional[str]
    description: Optional[str]
    page_narration: Optional[str]
    dialogues: Optional[List[Dict[str, str]]]
    narration_audio_url: Optional[str]
    
    model_config = ORMConfig


class ComicWithPanels(ComicDetail):
    """Comic with panels"""
    panels: List[ComicPanel] = []
    
    model_config = ORMConfig


# ============ Master Data Schemas ============

from pydantic import computed_field

class StyleResponse(BaseModel):
    """Style response schema"""
    id: int
    name: str
    description: Optional[str]
    image_url: Optional[str]
    
    @computed_field
    def key(self) -> str:
        return str(self.id)
    
    model_config = ORMConfig


class GenreResponse(BaseModel):
    """Genre response schema"""
    id: int
    name: str
    description: Optional[str]
    
    @computed_field
    def key(self) -> str:
        return str(self.id)
    
    model_config = ORMConfig


class CharacterResponse(BaseModel):
    """Character response schema"""
    id: int
    name: str
    image_url: Optional[str]
    description_prompt: Optional[str]
    
    @computed_field
    def key(self) -> str:
        return str(self.id)
    
    model_config = ORMConfig


class BackgroundResponse(BaseModel):
    """Background response schema"""
    id: int
    name: str
    image_url: Optional[str]
    description_prompt: Optional[str]
    
    @computed_field
    def key(self) -> str:
        return str(self.id)
    
    model_config = ORMConfig
