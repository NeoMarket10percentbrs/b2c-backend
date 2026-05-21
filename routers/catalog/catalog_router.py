from uuid import UUID
from fastapi import APIRouter, Query
from services.b2b import get_b2b_client


catalog_router = APIRouter(prefix="/catalog", tags=["Catalog"])


@catalog_router.get("/products")
async def list_products(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=200),
    sort: str = Query(default="popularity"),
    filter_category_id: UUID | None = Query(default=None, alias="filter[category_id]"),
    filter_price_min: int | None = Query(default=None, ge=0, alias="filter[price_min]"),
    filter_price_max: int | None = Query(default=None, ge=0, alias="filter[price_max]"),
    filter_seller_id: UUID | None = Query(default=None, alias="filter[seller_id]"),
):
    return await get_b2b_client().list_products(
        category_id=filter_category_id,
        search=q,
        min_price=filter_price_min,
        max_price=filter_price_max,
        seller_id=filter_seller_id,
        page=1 + (offset // limit),
        size=limit,
        sort=sort,
    )


@catalog_router.get("/products/{product_id}")
async def get_product(product_id: UUID):
    return await get_b2b_client().get_product(product_id)


@catalog_router.get("/products/{product_id}/similar")
async def get_similar(product_id: UUID, limit: int = Query(default=10, ge=1, le=50)):
    return await get_b2b_client().get_similar_products(product_id, limit=limit)


@catalog_router.get("/categories")
async def get_categories():
    return await get_b2b_client().get_categories()


@catalog_router.get("/categories/tree")
async def get_categories_tree():
    return await get_b2b_client().get_categories_tree()


@catalog_router.get("/banners")
async def get_banners():
    return await get_b2b_client().get_banners()


@catalog_router.get("/collections")
async def get_collections():
    return await get_b2b_client().get_collections()
