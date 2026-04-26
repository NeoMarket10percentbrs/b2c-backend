from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FavoriteAdd(BaseModel):
    product_id: UUID
    notify_in_stock: bool = False
    notify_price_down: bool = False


class FavoriteUpdate(BaseModel):
    notify_in_stock: bool | None = None
    notify_price_down: bool | None = None


class FavoriteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    notify_in_stock: bool
    notify_price_down: bool
    baseline_price: int | None
    created_at: datetime
    product_name: str | None = None
    current_price: int | None = None
    image_url: str | None = None
    in_stock: bool | None = None
