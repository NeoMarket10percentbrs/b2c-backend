from uuid import UUID
from fastapi import APIRouter, Query
from services.b2b import get_b2b_client


catalog_router = APIRouter(prefix="/catalog", tags=["catalog"])


@catalog_router.get("/products")
async def list_products(
    category_id: UUID | None = None,
    search: str | None = None,
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    seller_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    return await get_b2b_client().list_products(
        category_id=category_id, search=search,
        min_price=min_price, max_price=max_price,
        seller_id=seller_id, page=page, size=size,
    )


@catalog_router.get("/products/{product_id}")
async def get_product(product_id: UUID):
    return await get_b2b_client().get_product(product_id)


@catalog_router.get("/products/{product_id}/similar")
async def get_similar(product_id: UUID, limit: int = Query(default=10, ge=1, le=50)):
    return await get_b2b_client().get_similar_products(product_id, limit=limit)


@catalog_router.get("/skus/{sku_id}")
async def get_sku(sku_id: UUID):
    return await get_b2b_client().get_sku(sku_id)


@catalog_router.get("/categories/tree")
async def get_categories_tree():
    return await get_b2b_client().get_categories_tree()


@catalog_router.get("/categories/{category_id}/breadcrumbs")
async def get_breadcrumbs(category_id: UUID):
    return await get_b2b_client().get_breadcrumbs(category_id)
