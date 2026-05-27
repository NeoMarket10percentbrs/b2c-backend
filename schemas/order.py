from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from models.order import OrderStatus
from schemas.address import AddressResponse
from schemas.payment_method import PaymentMethodResponse


class OrderCreateRequest(BaseModel):
	address_id: UUID
	payment_method_id: UUID
	comment: str | None = Field(default=None, max_length=1000)
	items_snapshot: list["OrderItemSnapshot"] | None = None


class OrderItemSnapshot(BaseModel):
	sku_id: UUID
	quantity: int = Field(ge=1)
	unit_price: int = Field(ge=0)


class OrderCancelRequest(BaseModel):
	reason: str | None = Field(default=None, max_length=500)


class OrderItem(BaseModel):
	model_config = ConfigDict(from_attributes=True)
	
	sku_id: UUID
	product_id: UUID
	name: str
	sku_code: str | None = None
	quantity: int
	unit_price: int
	line_total: int
	image_url: str | None = None


class OrderResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	number: str | None = None
	buyer_id: UUID
	status: OrderStatus
	status_history: list[dict] | None = None
	items: list[OrderItem]
	subtotal: int
	delivery_cost: int = 0
	total: int
	address: AddressResponse
	payment_method: PaymentMethodResponse | None = None
	comment: str | None
	cancel_reason: str | None = None
	created_at: datetime
	paid_at: datetime | None = None
	delivered_at: datetime | None = None


class OrderShortResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	status: OrderStatus
	total: int
	created_at: datetime


class PaginatedOrders(BaseModel):
	items: list[OrderResponse]
	total_count: int
	limit: int
	offset: int
