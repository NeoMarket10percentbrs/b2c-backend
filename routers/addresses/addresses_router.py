from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.dependencies import get_current_buyer
from models.buyer import Buyer
from schemas.address import AddressCreateRequest, AddressResponse, AddressUpdateRequest
from services import address_service

addresses_router = APIRouter(prefix="/buyers/me/addresses", tags=["Addresses"])


@addresses_router.get("", response_model=list[AddressResponse])
async def list_addresses(
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    return await address_service.list_addresses(db, buyer.id)


@addresses_router.post("", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_address(
    payload: AddressCreateRequest, 
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    return await address_service.create_address(db, buyer.id, payload)


@addresses_router.patch("/{address_id}", response_model=AddressResponse)
async def update_address(
    address_id: UUID, payload: AddressUpdateRequest,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    return await address_service.update_address(db, address_id, buyer.id, payload)


@addresses_router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: UUID, 
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    await address_service.delete_address(db, address_id, buyer.id)