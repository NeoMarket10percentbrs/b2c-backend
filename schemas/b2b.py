from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class EventProductRef(BaseModel):
    product_id: UUID
    reason: str | None = None


class EventSkuStock(BaseModel):
    sku_id: UUID
    product_id: UUID
    available_quantity: int = Field(ge=0)


class EventPriceChanged(BaseModel):
    sku_id: UUID
    product_id: UUID
    old_price: int
    new_price: int


class B2BEvent(BaseModel):
    event_type: str
    idempotency_key: UUID
    occurred_at: datetime
    payload: EventProductRef | EventSkuStock | EventPriceChanged
