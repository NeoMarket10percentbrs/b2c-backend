from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class AddressCreate(BaseModel):
	label: str | None = None
	country: str
	city: str
	street: str
	building: str
	apartment: str | None = None
	postal_code: str


class AddressUpdate(BaseModel):
	label: str | None = None
	country: str | None = None
	city: str | None = None
	street: str | None = None
	building: str | None = None
	apartment: str | None = None
	postal_code: str | None = None


class AddressResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	label: str | None
	country: str
	city: str
	street: str
	building: str
	apartment: str | None
	postal_code: str
	is_default: bool
	created_at: datetime
