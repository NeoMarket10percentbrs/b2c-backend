from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BannerCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    image_url: str = Field(min_length=1, max_length=1000)
    link_url: str | None = Field(default=None, max_length=1000)
    priority: int = 0
    starts_at: datetime
    ends_at: datetime
    is_active: bool = True


class BannerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    image_url: str
    link_url: str | None
    priority: int
    starts_at: datetime
    ends_at: datetime
    is_active: bool
