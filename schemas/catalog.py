from uuid import UUID
from pydantic import BaseModel, Field


class CategoryRef(BaseModel):
    id: UUID
    name: str
    parent_id: UUID | None = None
    level: int = Field(ge=0)
    path: str


class CategoryTreeNode(BaseModel):
    id: UUID
    name: str
    parent_id: UUID | None = None
    level: int | None = None
    path: str | None = None
    children: list["CategoryTreeNode"] = []


class CatalogFilter(BaseModel):
    category_id: UUID | None = None
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    seller_id: UUID | None = None
    attributes: dict | None = None


class ImageRef(BaseModel):
    id: UUID
    url: str
    alt: str | None = None
    ordering: int = Field(ge=0)
    is_main: bool | None = None


class CatalogProductCard(BaseModel):
    id: UUID
    title: str
    slug: str | None = None
    category_id: UUID | None = None
    min_price: int | None = None
    old_price: int | None = None
    # has_stock: bool
    rating: float | None = None
    reviews_count: int = Field(default=0, ge=0)
    cover_image: str | None = None
    seller: dict | None = None


class CatalogSku(BaseModel):
    id: UUID
    name: str | None = None
    sku_code: str | None = None
    price: int
    old_price: int | None = None
    active_quantity: int = Field(ge=0)
    attributes: dict | None = None
    images: list[ImageRef] = []


class CatalogProductDetail(CatalogProductCard):
    description: str
    attributes: dict | None = None
    skus: list[CatalogSku]


class PaginatedCatalogProducts(BaseModel):
    items: list[CatalogProductCard]
    total_count: int
    limit: int
    offset: int


class Banner(BaseModel):
    id: UUID
    title: str | None = None
    image_url: str
    link: str
    ordering: int | None = None
    active_from: str | None = None
    active_to: str | None = None


class Collection(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    products: list[CatalogProductCard]
