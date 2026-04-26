from uuid import UUID
from pydantic import BaseModel


class CategoryShort(BaseModel):
    id: UUID
    name: str
    slug: str | None = None
    parent_id: UUID | None = None


class CategoryTreeNode(CategoryShort):
    children: list["CategoryTreeNode"] = []


class BreadcrumbItem(BaseModel):
    id: UUID
    name: str
    slug: str | None = None


class SkuShort(BaseModel):
    id: UUID
    article: str | None = None
    price: int
    stock_quantity: int
    image_url: str | None = None
    attributes: dict | None = None


class ProductShort(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    seller_id: UUID
    category_id: UUID
    image_url: str | None = None
    min_price: int | None = None


class ProductDetail(ProductShort):
    images: list[str] = []
    skus: list[SkuShort] = []


class ProductListResponse(BaseModel):
    total: int
    items: list[ProductShort]
