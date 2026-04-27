from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.dependencies import get_current_buyer
from models.buyer import Buyer
from schemas.payment_method import (
    PaymentMethodCreate, PaymentMethodResponse, PaymentMethodUpdate
)
from services import payment_service

payment_router = APIRouter(prefix="/payment-methods", tags=["payment-methods"])


@payment_router.get("", response_model=list[PaymentMethodResponse])
async def list_methods(
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    return await payment_service.list_payment_methods(db, buyer.id)


@payment_router.post("", response_model=PaymentMethodResponse, status_code=status.HTTP_201_CREATED)
async def create_method(
    payload: PaymentMethodCreate,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    return await payment_service.create_payment_method(
        db, buyer.id, payload
    )


@payment_router.patch("/{method_id}", response_model=PaymentMethodResponse)
async def update_method(
    method_id: UUID, payload: PaymentMethodUpdate,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    return await payment_service.update_payment_method(
        db, buyer.id, method_id, payload
    )


@payment_router.delete("/{method_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_method(
    method_id: UUID,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    await payment_service.delete_payment_method(
        db, buyer.id, method_id
    )