from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.dependencies import get_current_buyer
from models.buyer import Buyer
from schemas.notification import (
    NotificationCreate, NotificationListResponse, NotificationResponse
)
from services import notification_service


notification_router = APIRouter(tags=["notifications"])


# Покупатель


@notification_router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    only_unread: bool = False,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    total, unread, items = await notification_service.list_notifications(
        db, buyer.id, only_unread=only_unread, page=page, size=size
    )
    return NotificationListResponse(
        total=total, unread=unread,
        items=[NotificationResponse.model_validate(i) for i in items],
    )


@notification_router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: UUID,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    notif = await notification_service.mark_read(db, buyer.id, notification_id)
    if notif is None:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    return notif


@notification_router.post("/notifications/read-all")
async def mark_all_read(
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    count = await notification_service.mark_all_read(db, buyer.id)
    return {"marked_read": count}


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
