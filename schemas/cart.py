from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from schemas.catalog import ImageRef


class CartItemAddRequest(BaseModel):
	sku_id: UUID
	quantity: int = Field(ge=1)


class CartItemUpdateRequest(BaseModel):
	quantity: int = Field(ge=1)


class CartItem(BaseModel):
	sku_id: UUID
	product_id: UUID | None = None
	name: str | None = None
	sku_code: str | None = None
	quantity: int
	unit_price: int | None = None
	unit_price_at_add: int | None = None
	line_total: int | None = None
	available_quantity: int | None = None
	is_available: bool = True
	image: ImageRef | None = None


class CartResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	items: list[CartItem]
	items_count: int
	subtotal: int
	is_valid: bool
	updated_at: datetime | None = None


class CartValidationIssue(BaseModel):
	sku_id: UUID
	type: str
	message: str
	old_value: str | int | None = None
	new_value: str | int | None = None


class CartValidationResponse(BaseModel):
	is_valid: bool
	cart: CartResponse
	issues: list[CartValidationIssue]
