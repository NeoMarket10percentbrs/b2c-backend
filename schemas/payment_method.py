from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class PaymentMethodCreateRequest(BaseModel):
    type: str = Field(pattern=r"^(CARD|SBP|WALLET)$")
    card_last4: str | None = Field(default=None, pattern=r"^[0-9]{4}$")
    card_brand: str | None = Field(default=None, pattern=r"^(VISA|MASTERCARD|MIR)$")
    is_default: bool = False


class PaymentMethodResponse(PaymentMethodCreateRequest):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
