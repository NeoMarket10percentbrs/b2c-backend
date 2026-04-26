from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from models.notification import NotificationType


class NotificationCreate(BaseModel):
    buyer_id: UUID
    type: NotificationType
    title: str
    body: str
    payload: dict[str, Any] = {}


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: NotificationType
    title: str
    body: str
    payload: dict[str, Any]
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    total: int
    unread: int
    items: list[NotificationResponse]
