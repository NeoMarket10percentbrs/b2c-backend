from pydantic import BaseModel, ConfigDict, computed_field
from uuid import UUID
from datetime import datetime
from models.order import OrderStatus
from schemas.address import AddressResponse


class OrderCreate(BaseModel):
	idempotency_key: UUID
	address_id: UUID
	payment_method_id: UUID | None = None
	comment: str | None = None


class OrderItemResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	sku_id: UUID
	product_id: UUID
	product_title: str
	seller_id: UUID
	sku_name: str
	image_url: str | None
	unit_price: int
	line_total: int
	quantity: int

	@computed_field
	@property
	def item_total(self) -> int:
		return self.line_total


class OrderResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	status: OrderStatus
	address: AddressResponse
	items: list[OrderItemResponse]
	total_price: int
	comment: str | None
	payment_method_id: UUID | None
	created_at: datetime
	updated_at: datetime


class OrderShortResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	status: OrderStatus
	total_price: int
	items_count: int
	created_at: datetime


class OrderListResponse(BaseModel):
	total: int
	items: list[OrderShortResponse]

class OrderStatusUpdate(BaseModel):
    status: OrderStatus
