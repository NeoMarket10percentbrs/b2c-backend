from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from pydantic_extra_types.phone_numbers import PhoneNumber
from uuid import UUID
from datetime import datetime


class BuyerCreate(BaseModel):
	email: EmailStr
	password: str = Field(min_length=8, max_length=128)
	first_name: str = Field(min_length=1, max_length=100)
	last_name: str = Field(min_length=1, max_length=100)
	phone: PhoneNumber | None = Field(default=None, max_length=20)

	@field_validator("first_name", "last_name")
	@classmethod
	def validate_required_name_parts(cls, value: str) -> str:
		normalized = value.strip()
		if not normalized:
			raise ValueError("Имя и фамилия не могут быть пустыми")
		return normalized


class BuyerUpdate(BaseModel):
	first_name: str | None = None
	last_name: str | None = None
	phone: PhoneNumber | None = None

	@field_validator("first_name", "last_name")
	@classmethod
	def validate_optional_required_name_parts(cls, value: str | None) -> str | None:
		if value is None:
			return None
		normalized = value.strip()
		if not normalized:
			raise ValueError("Имя и фамилия не могут быть пустыми")
		return normalized


class BuyerResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	email: str
	first_name: str
	last_name: str
	phone: PhoneNumber | None
	avatar_url: str | None
	is_active: bool
	created_at: datetime
	updated_at: datetime
