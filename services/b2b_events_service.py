from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from models.b2b_event import B2BEvent
from schemas.b2b import B2BEvent as B2BEventPayload


async def handle_event(db: AsyncSession, event: B2BEventPayload) -> None:
    now = datetime.now(timezone.utc)
    await _cleanup_expired(db, now)

    existing = await db.execute(
        select(B2BEvent).where(
            B2BEvent.idempotency_key == event.idempotency_key,
            B2BEvent.expires_at >= now,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="DUPLICATE_EVENT",
        )

    record = B2BEvent(
        idempotency_key=event.idempotency_key,
        event_type=event.event_type,
        payload=event.model_dump(mode="json"),
        expires_at=now + timedelta(hours=24),
    )
    db.add(record)
    await db.commit()


async def _cleanup_expired(db: AsyncSession, now: datetime) -> None:
    await db.execute(
        delete(B2BEvent).where(B2BEvent.expires_at < now)
    )
    await db.commit()
