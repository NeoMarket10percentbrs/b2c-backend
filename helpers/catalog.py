from uuid import UUID, uuid4
from schemas.catalog import (
    CatalogProductCard, CatalogProductDetail, CategoryTreeNode,
    ImageRef, CategoryRef, SellerRef
)
from collections import defaultdict
from schemas.catalog import Facet, FacetValue

def _safe_price(value):
    return int(value) if value is not None else 0

def _available_quantity(skus: list[dict]) -> int:
    return sum(s.get("active_quantity", 0) for s in skus)

def _normalize_path(raw_path) -> list[str]:
    if isinstance(raw_path, str):
        return [x for x in raw_path.split("/") if x]
    if isinstance(raw_path, list):
        return raw_path
    return []

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
        path=_normalize_path(cat.get("path"))
    )

    seller = b2b_product.get("seller")
    if not seller:
        seller = {"id": b2b_product.get("seller_id"), "company_name": None}
    seller_ref = SellerRef(
        id=UUID(seller["id"]),
        display_name=seller.get("company_name") or "",
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
    skus = []
    for s in b2b_product.get("skus", []):
        sku_characteristics = s.get("characteristics")
        if isinstance(sku_characteristics, list):
            attrs = {c["name"]: c.get("value") for c in sku_characteristics if "name" in c}
        else:
            attrs = sku_characteristics
        sku_dict = {
            "id": s["id"],
            "product_id": s.get("product_id"),
            "name": s.get("name"),
            "sku_code": s.get("sku_code"),
            "price": int(s.get("price", 0)),
            "old_price": (int(s.get("price", 0)) + int(s.get("discount", 0))) if int(s.get("discount", 0)) > 0 else None,
            "available_quantity": int(s.get("active_quantity", 0)),
            "is_available": int(s.get("active_quantity", 0)) > 0,
            "attributes": attrs,
            "images": [ImageRef(id=i.get("id"), url=i["url"], alt=i.get("alt"), ordering=i.get("ordering",0), is_main=i.get("ordering")==0) for i in s.get("images", [])],
        }
        skus.append(sku_dict)

    return CatalogProductDetail(
        **base.model_dump(),
        description=b2b_product.get("description") or "",
        characteristics=b2b_product.get("characteristics", []),
        skus=skus,
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


def adapt_category_ref(cat: dict) -> CategoryRef:
    return CategoryRef(
        id=UUID(cat["id"]),
        name=cat.get("name") or "",
        parent_id=cat.get("parent_id"),
        level=cat.get("level", 0),
        path=_normalize_path(cat.get("path")),
    )


def adapt_category_tree_node(raw: dict) -> CategoryTreeNode:
    return CategoryTreeNode(
        id=UUID(raw["id"]),
        name=raw.get("name") or "",
        parent_id=raw.get("parent_id"),
        level=raw.get("level") or 0,
        path=_normalize_path(raw.get("path")),
        children=[adapt_category_tree_node(child) for child in raw.get("children", [])]
    )