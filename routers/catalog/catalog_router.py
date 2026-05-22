from uuid import UUID
from fastapi import APIRouter, Query, Request
from services.b2b import get_b2b_client
from schemas.catalog import (
    PaginatedCatalogProducts, CatalogProductDetail,
    CatalogProductCard, CategoryRef, CategoryTreeNode,
    Banner, Collection
)
from enum import Enum
from helpers.catalog import adapt_product_card, adapt_product_detail, aggregate_facets


class SortEnum(str, Enum):
    popularity = "popularity"
    price_asc = "price_asc"
    price_desc = "price_desc"
    new = "new"

catalog_router = APIRouter(prefix="/catalog", tags=["Catalog"])


def _parse_filters(request: Request) -> dict[str, list[str]] | None:
    result: dict[str, list[str]] = {}
    for key, value in request.query_params.multi_items():
        if key.startswith("filters[") and key.endswith("]"):
            attr = key[8:-1]
            if attr:
                result.setdefault(attr, []).append(value)
    return result if result else None


@catalog_router.get("/products", response_model=PaginatedCatalogProducts)
async def list_products(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=200),
    sort: str = Query(default="popularity"),
    filter_category_id: UUID | None = Query(default=None, alias="filter[category_id]"),
    filter_price_min: int | None = Query(default=None, ge=0, alias="filter[price_min]"),
    filter_price_max: int | None = Query(default=None, ge=0, alias="filter[price_max]"),
    filter_seller_id: UUID | None = Query(default=None, alias="filter[seller_id]"),
):
    b2b = get_b2b_client()
    filters = _parse_filters(request)
    data = await b2b.list_products(
        category_id=filter_category_id,
        search=q,
        min_price=filter_price_min,
        max_price=filter_price_max,
        seller_id=filter_seller_id,
        filters=filters,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    items = data.get("items", [])
    total_count = data.get("total_count", 0)
    if not items:
        return PaginatedCatalogProducts(
            items=[], total_count=total_count, limit=limit, offset=offset, facets=[]
        )

    product_ids = [UUID(item["id"]) for item in items]
    full_products = await b2b.get_products_by_ids(product_ids)
    cards = [adapt_product_card(full_products[pid]) for pid in product_ids if pid in full_products]
    facets = aggregate_facets(list(full_products.values()))

    return PaginatedCatalogProducts(
        items=cards,
        total_count=total_count,
        limit=limit,
        offset=offset,
        facets=facets,
    )


@catalog_router.get("/products/{product_id}", response_model=CatalogProductDetail)
async def get_product(product_id: UUID):
    product = await get_b2b_client().get_product(product_id)
    return adapt_product_detail(product) 


@catalog_router.get("/products/{product_id}/similar", response_model=list[CatalogProductCard])
async def get_similar(product_id: UUID, limit: int = Query(default=10, ge=1, le=50)):
    return await get_b2b_client().get_similar_products(product_id, limit=limit)


@catalog_router.get("/categories", response_model=list[CategoryRef])
async def get_categories():
    return await get_b2b_client().get_categories()


@catalog_router.get("/categories/tree", response_model=list[CategoryTreeNode])
async def get_categories_tree():
    return await get_b2b_client().get_categories_tree()


@catalog_router.get("/banners", response_model=list[Banner])
async def get_banners():
    return await get_b2b_client().get_banners()


@catalog_router.get("/collections", response_model=list[Collection])
async def get_collections():
    return await get_b2b_client().get_collections()


@catalog_router.get("/categories/{category_id}/breadcrumbs", response_model=list[CategoryRef])
async def get_breadcrumbs(category_id: UUID):
    return await get_b2b_client().get_breadcrumbs(category_id)
