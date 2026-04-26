from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from schemas.catalog import ProductShort


class CollectionItemCreate(BaseModel):
    product_id: UUID
    position: int = 0


class CollectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True


class CollectionShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str
    description: str | None
    is_active: bool


class CollectionDetail(CollectionShort):
    products: list[ProductShort] = []
