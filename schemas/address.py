from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class AddressCreateRequest(BaseModel):
    country: str = Field(max_length=100)
    region: str | None = Field(default=None, max_length=200)
    city: str = Field(max_length=200)
    street: str = Field(max_length=200)
    building: str = Field(max_length=50)
    apartment: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    recipient_name: str | None = Field(default=None, max_length=200)
    recipient_phone: str | None = Field(default=None, pattern=r"^\+?[0-9]{10,15}$")
    is_default: bool = False
    comment: str | None = Field(default=None, max_length=500)


class AddressUpdateRequest(AddressCreateRequest):
    pass


class AddressResponse(AddressCreateRequest):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
