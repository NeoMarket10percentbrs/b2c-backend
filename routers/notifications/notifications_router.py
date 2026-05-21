from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.dependencies import get_current_buyer
from models.buyer import Buyer
from schemas.notification import (
    NotificationCreate, PaginatedNotifications, NotificationResponse
)
from services import notification_service


notification_router = APIRouter(prefix="/notifications", tags=["Notifications"])


# Покупатель


@notification_router.get("", response_model=PaginatedNotifications)
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    total, unread, items = await notification_service.list_notifications(
        db, buyer.id, only_unread=unread_only, limit=limit, offset=offset
    )
    return PaginatedNotifications(
        total_count=total, unread_count=unread,
        limit=limit, offset=offset,
        items=[NotificationResponse.model_validate(i) for i in items],
    )


@notification_router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    notification_id: UUID, buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    notif = await notification_service.mark_read(db, buyer.id, notification_id)
    if notif is None:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    return None


# Внутренний эндпоинт


# @notification_router.post(
#     "/internal/notifications",
#     response_model=NotificationResponse,
#     status_code=status.HTTP_201_CREATED,
#     # dependencies=[Depends(require_internal_token)],
# )
# async def create_notification(
#     payload: NotificationCreate, db: AsyncSession = Depends(get_db)
# ):
#     """
#     Используется внутренней логикой и B2B сервисом для создания
#     уведомлений (смена статуса заказа, появление товара в наличии, снижение цены).
#     Защищён X-Internal-Token.
#     """
#     return await notification_service.create_notification(
#         db, buyer_id=payload.buyer_id,
#         type_=payload.type,
#         title=payload.title,
#         body=payload.body,
#         payload=payload.payload,
#     )
