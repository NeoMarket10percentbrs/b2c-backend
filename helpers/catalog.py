from uuid import UUID, uuid4
from schemas.catalog import (
    CatalogProductCard, CatalogProductDetail,
    ImageRef, CategoryRef, SellerRef
)
from collections import defaultdict
from schemas.catalog import Facet, FacetValue

def _safe_price(value):
    return int(value) if value is not None else 0

def _available_quantity(skus: list[dict]) -> int:
    return sum(s.get("active_quantity", 0) for s in skus)

def adapt_product_card(b2b_product: dict) -> CatalogProductCard:
    skus = b2b_product.get("skus", [])
    available_qty = _available_quantity(skus)
    min_price = b2b_product.get("min_price") or _safe_price(b2b_product.get("price"))
    old_price = b2b_product.get("old_price") or b2b_product.get("price_old")

    cat = b2b_product.get("category")
    if not cat:
        # если B2B отдаёт только category_id – подставляем заглушку
        cat = {"id": b2b_product.get("category_id"), "name": None, "parent_id": None, "level": 0, "path": ""}
    category_ref = CategoryRef(
        id=UUID(cat["id"]),
        name=cat.get("name") or "",
        parent_id=cat.get("parent_id"),
        level=cat.get("level", 0),
        path=cat.get("path", ""),
    )

    seller = b2b_product.get("seller")
    if not seller:
        seller = {"id": b2b_product.get("seller_id"), "company_name": None}
    seller_ref = SellerRef(
        id=UUID(seller["id"]),
        company_name=seller.get("company_name") or "",
    )

    images = []
    for img in b2b_product.get("images", []):
        images.append(ImageRef(
            id=img.get("id"),
            url=img["url"],
            alt=img.get("alt"),
            ordering=img.get("ordering", 0),
            is_main=img.get("ordering") == 0
        ))
    if not images and b2b_product.get("cover_image"):
        images.append(ImageRef(url=b2b_product["cover_image"], ordering=0, is_main=True))

    return CatalogProductCard(
        id=UUID(b2b_product["id"]),
        name=b2b_product.get("title") or b2b_product.get("name") or "",
        slug=b2b_product.get("slug") or "",
        min_price=min_price,
        old_price=old_price,
        has_stock=available_qty > 0,
        available_quantity=available_qty,
        rating=b2b_product.get("rating"),
        reviews_count=b2b_product.get("reviews_count") or 0,
        category=category_ref,
        images=images,
        seller=seller_ref,
    )

def adapt_product_detail(b2b_product: dict) -> CatalogProductDetail:
    base = adapt_product_card(b2b_product)
    return CatalogProductDetail(
        **base.model_dump(),
        description=b2b_product.get("description") or "",
        characteristics=b2b_product.get("characteristics", []),
        skus=b2b_product.get("skus", []),
        created_at=b2b_product["created_at"],
        updated_at=b2b_product["updated_at"],
    )


def aggregate_facets(products: list[dict]) -> list[Facet]:
    facet_dict = defaultdict(lambda: defaultdict(int))
    for product in products:
        for char in product.get("characteristics", []):
            name = char.get("name")
            value = char.get("value")
            if name and value is not None:
                facet_dict[name][str(value)] += 1

    facets = []
    for name, values in facet_dict.items():
        facets.append(Facet(
            name=name,
            values=[FacetValue(value=v, count=c) for v, c in values.items()]
        ))
    return facets