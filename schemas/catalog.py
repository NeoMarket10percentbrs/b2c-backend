from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class CategoryRef(BaseModel):
    id: UUID
    name: str
    parent_id: UUID | None = None
    level: int = Field(ge=0)
    path: list[str]


class SellerRef(BaseModel):
    id: UUID
    display_name: str


class CategoryTreeNode(BaseModel):
    id: UUID
    name: str
    parent_id: UUID | None = None
    level: int
    path: list[str] 
    children: list["CategoryTreeNode"] = []


class CatalogFilter(BaseModel):
    category_id: UUID | None = None
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    seller_id: UUID | None = None
    attributes: dict | None = None


class ImageRef(BaseModel):
    id: UUID | None = None
    url: str
    alt: str | None = None
    ordering: int = Field(ge=0)
    is_main: bool = False


class CatalogProductCard(BaseModel):
    id: UUID
    name: str
    slug: str
    min_price: int
    old_price: int | None = None
    has_stock: bool
    available_quantity: int
    rating: float | None = None
    reviews_count: int = Field(ge=0, default=0)
    category: CategoryRef
    images: list[ImageRef]
    seller: SellerRef


class CatalogSku(BaseModel):
    id: UUID
    name: str | None = None
    sku_code: str | None = None
    price: int
    old_price: int | None = None
    available_quantity: int = Field(ge=0)
    is_available: bool = True
    attributes: dict | None = None
    images: list[ImageRef] = []


class CatalogProductDetail(CatalogProductCard):
    description: str
    characteristics: list[dict] = []  # пока оставим, но можно заменить на характеристики
    skus: list[dict]                 # SKU без себестоимости
    created_at: datetime
    updated_at: datetime


class PaginatedCatalogProducts(BaseModel):
    items: list[CatalogProductCard]
    total_count: int
    limit: int
    offset: int
    facets: list["Facet"] = []  


class FacetValue(BaseModel):
    value: str
    count: int

class Facet(BaseModel):
    name: str
    values: list[FacetValue]


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
