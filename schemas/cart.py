from pydantic import BaseModel, ConfigDict, Field, field_validator, computed_field
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
	quantity: int = Field(gt=0)

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
    
    product_id: UUID | None = None
    sku_name: str | None = None
    sku_price: int | None = None
    image_url: str | None = None
    stock_quantity: int | None = None
    is_available: bool = True


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
	
	@computed_field
	@property
	def items_count(self) -> int:
		return sum(item.quantity for item in self.items)
	

class CartValidationIssue(BaseModel):
    sku_id: UUID
    reason: str  # "not_found" | "out_of_stock" | "insufficient_stock"
    requested: int
    available: int | None = None

class CartValidationResponse(BaseModel):
	is_valid: bool
	issues: list[CartValidationIssue]
