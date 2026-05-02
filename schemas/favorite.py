from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FavoriteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    created_at: datetime
    product_name: str | None = None
    current_price: int | None = None
    image_url: str | None = None
    in_stock: bool | None = None


class FavoriteListResponse(BaseModel):
    items: list[FavoriteResponse]
    total_count: int
    limit: int
    offset: int


class SubscribeRequest(BaseModel):
    notify_on: list[str]
