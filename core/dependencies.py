from uuid import UUID
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import decode_access_token
from models.buyer import Buyer
from services.buyer_service import get_buyer_by_id
from core.config import settings


security = HTTPBearer()


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


async def get_current_buyer(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Buyer:
    token = credentials.credentials
    try:
        buyer_id = decode_access_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    buyer = await get_buyer_by_id(db, buyer_id)
    if not buyer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Покупатель не найден",
        )
    if not buyer.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт деактивирован",
        )

    return buyer

    
async def require_internal_token(
    x_internal_token: str = Header(alias="X-Internal-Token")
):
    if x_internal_token != settings.B2B_INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недействительный внутренний токен"
        )


async def get_cart_identity(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> dict[str, UUID | str | None]:
    if authorization:
        token = _extract_bearer_token(authorization)
        try:
            buyer_id = decode_access_token(token)
            buyer_uuid = UUID(buyer_id)
        except (JWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невалидный токен",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"buyer_id": buyer_uuid, "session_id": None}

    if x_session_id:
        return {"buyer_id": None, "session_id": x_session_id}

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="MISSING_CART_IDENTITY",
    )