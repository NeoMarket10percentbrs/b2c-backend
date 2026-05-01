from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import decode_access_token
from models.buyer import Buyer
from services.buyer_service import get_buyer_by_id
from core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_buyer(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> Buyer:
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