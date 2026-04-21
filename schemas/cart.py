from pydantic import BaseModel, ConfigDict, field_validator, computed_field
from uuid import UUID


class CartItemAdd(BaseModel):
	sku_id: UUID
	quantity: int

	@field_validator("quantity")
	@classmethod
	def must_be_positive(cls, value: int) -> int:
		if value <= 0:
			raise ValueError("Количество должно быть больше нуля")
		return value


class CartItemUpdate(BaseModel):
	quantity: int

	@field_validator("quantity")
	@classmethod
	def must_be_positive(cls, value: int) -> int:
		if value <= 0:
			raise ValueError("Количество должно быть больше нуля")
		return value


class CartItemResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	sku_id: UUID
	quantity: int
	# sku_info подтягивается из Seller Service (не из БД)
	sku_name: str | None = None
	sku_price: int | None = None


class CartResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: UUID
	items: list[CartItemResponse]

	@computed_field
	@property
	def total_price(self) -> int:
		total = 0
		for item in self.items:
			if item.sku_price is None:
				continue
			total += item.sku_price * item.quantity
		return total
