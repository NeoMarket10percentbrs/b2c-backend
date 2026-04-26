from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentMethodCreate(BaseModel):
    cardholder_name: str = Field(min_length=1, max_length=255)
    card_number: str = Field(min_length=12, max_length=19)
    exp_month: int = Field(ge=1, le=12)
    exp_year: int = Field(ge=2000, le=2100)
    is_default: bool = False

    @field_validator("card_number")
    @classmethod
    def only_digits(cls, value: str) -> str:
        clean = value.replace(" ", "").replace("-", "")
        if not clean.isdigit():
            raise ValueError("Номер карты должен содержать только цифры")
        return clean


class PaymentMethodUpdate(BaseModel):
    cardholder_name: str | None = Field(default=None, min_length=1, max_length=255)
    exp_month: int | None = Field(default=None, ge=1, le=12)
    exp_year: int | None = Field(default=None, ge=2000, le=2100)
    is_default: bool | None = None


class PaymentMethodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cardholder_name: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool
    created_at: datetime
