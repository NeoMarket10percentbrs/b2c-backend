from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.dependencies import require_service_key
from schemas.b2b import B2BEvent
from services import b2b_events_service


b2b_events_router = APIRouter(prefix="/b2b", tags=["B2B Events"])


@b2b_events_router.post(
    "/events", status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_service_key)]
)
async def receive_event(payload: B2BEvent, db: AsyncSession = Depends(get_db)):
    await b2b_events_service.handle_event(db, payload)
    return None
