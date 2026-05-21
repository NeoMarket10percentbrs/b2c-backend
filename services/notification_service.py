from typing import Any
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from models.notification import Notification, NotificationType


async def create_notification(
    db: AsyncSession, buyer_id: UUID, type_: NotificationType,
    title: str, body: str, payload: dict[str, Any] | None = None
) -> Notification:
    notification = Notification(
        buyer_id=buyer_id, type=type_, title=title,
        body=body, payload=payload or {},
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


async def list_notifications(
    db: AsyncSession, buyer_id: UUID,
    *, only_unread: bool, limit: int, offset: int
):
    base = select(Notification).where(Notification.buyer_id == buyer_id)
    if only_unread:
        base = base.where(Notification.is_read.is_(False))

    total = (
        await db.execute(
            select(func.count()).select_from(base.subquery())
        )
    ).scalar_one()
    unread = (
        await db.execute(
            select(func.count(Notification.id)).where(
                Notification.buyer_id == buyer_id,
                Notification.is_read.is_(False)
            )
        )
    ).scalar_one()

    items_q = (
        base.order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = (await db.execute(items_q)).scalars().all()
    return total, unread, list(items)


async def mark_read(db: AsyncSession, buyer_id: UUID, notification_id: UUID) -> Notification | None:
    notif = await db.get(Notification, notification_id)
    if notif is None or notif.buyer_id != buyer_id:
        return None
    notif.is_read = True
    await db.commit()
    await db.refresh(notif)
    return notif


async def mark_all_read(db: AsyncSession, buyer_id: UUID) -> int:
    result = await db.execute(
        select(Notification).where(
            Notification.buyer_id == buyer_id,
            Notification.is_read.is_(False),
        )
    )
    count = 0
    for notif in result.scalars().all():
        notif.is_read = True
        count += 1
    await db.commit()
    return count
