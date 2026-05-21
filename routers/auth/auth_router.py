from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from schemas.auth import TokenResponse, RefreshRequest, LoginRequest
from schemas.buyer import BuyerRegisterRequest
from services import auth_service
from core.dependencies import get_current_buyer
from models.buyer import Buyer

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.post(
	"/register", response_model=TokenResponse,
	status_code=status.HTTP_201_CREATED,
	summary="Регистрация покупателя"
)
async def register(data: BuyerRegisterRequest, db: AsyncSession = Depends(get_db)):
	return await auth_service.register(db, data)


@auth_router.post("/login", response_model=TokenResponse)
async def login(
	data: LoginRequest,
	x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
	db: AsyncSession = Depends(get_db),
):
	return await auth_service.login(db, data.email, data.password, x_session_id)


@auth_router.post("/refresh", response_model=TokenResponse, summary="Обновить токены")
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
	return await auth_service.refresh_tokens(db, data.refresh_token)


@auth_router.post(
	"/logout",
	status_code=status.HTTP_204_NO_CONTENT,
	summary="Выход",
)
async def logout(buyer: Buyer = Depends(get_current_buyer), db: AsyncSession = Depends(get_db)):
	await auth_service.revoke_all_buyer_tokens(db, buyer.id)
