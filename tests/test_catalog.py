import pytest
from uuid import uuid4, UUID
from httpx import AsyncClient, ASGITransport
from main import app
from asgi_lifespan import LifespanManager
import httpx
from unittest.mock import patch, AsyncMock


# Helpers

CATEGORY_ID: UUID | None = None


def paginated_ok(data: dict):
    assert "items" in data
    assert "total_count" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total_count"], int)


# Fixture

@pytest.fixture(scope="session")
async def client():
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# Tests

async def test_catalog_returns_products(client):
    response = await client.get("/api/v1/catalog/products")

    assert response.status_code == 200
    data = response.json()
    paginated_ok(data)


async def test_catalog_filter_by_category(client):
    cats = await client.get("/api/v1/catalog/categories")
    assert cats.status_code == 200
    categories = cats.json()

    if not categories:
        pytest.skip("Нет категорий в B2B")

    category_id = categories[0]["id"]

    response = await client.get(
        "/api/v1/catalog/products",
        params={"filter[category_id]": category_id},
    )

    assert response.status_code == 200
    data = response.json()
    paginated_ok(data)


async def test_catalog_filter_by_price(client):
    response = await client.get(
        "/api/v1/catalog/products",
        params={"filter[price_min]": 0, "filter[price_max]": 9_999_999},
    )

    assert response.status_code == 200
    data = response.json()
    paginated_ok(data)
    for item in data["items"]:
        assert item["min_price"] >= 0


async def test_catalog_sort_price_asc(client):
    response = await client.get(
        "/api/v1/catalog/products",
        params={"sort": "price_asc", "limit": 10},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    prices = [i["min_price"] for i in items]
    assert prices == sorted(prices)


async def test_catalog_sort_price_desc(client):
    response = await client.get(
        "/api/v1/catalog/products",
        params={"sort": "price_desc", "limit": 10},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    prices = [i["min_price"] for i in items]
    assert prices == sorted(prices, reverse=True)


async def test_catalog_search(client):
    response = await client.get(
        "/api/v1/catalog/products",
        params={"q": "ааа"},
    )

    assert response.status_code == 200
    paginated_ok(response.json())


async def test_catalog_pagination(client):
    page1 = await client.get(
        "/api/v1/catalog/products",
        params={"limit": 2, "offset": 0},
    )
    page2 = await client.get(
        "/api/v1/catalog/products",
        params={"limit": 2, "offset": 2},
    )

    assert page1.status_code == 200
    assert page2.status_code == 200

    ids1 = {i["id"] for i in page1.json()["items"]}
    ids2 = {i["id"] for i in page2.json()["items"]}

    assert ids1.isdisjoint(ids2)


async def test_get_product_by_id(client):
    products = await client.get("/api/v1/catalog/products", params={"limit": 1})
    assert products.status_code == 200
    items = products.json()["items"]

    if not items:
        pytest.skip("Нет товаров в B2B")

    product_id = items[0]["id"]
    response = await client.get(f"/api/v1/catalog/products/{product_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == product_id
    assert "skus" in data


async def test_get_product_not_found(client):
    fake_id = uuid4()
    response = await client.get(f"/api/v1/catalog/products/{fake_id}")

    assert response.status_code == 404
    data = response.json()
    assert "code" in data
    assert "message" in data


async def test_get_similar_products(client):
    products = await client.get("/api/v1/catalog/products", params={"limit": 1})
    items = products.json()["items"]

    if not items:
        pytest.skip("Нет товаров в B2B")

    product_id = items[0]["id"]
    response = await client.get(f"/api/v1/catalog/products/{product_id}/similar")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_get_categories(client):
    response = await client.get("/api/v1/catalog/categories")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_get_categories_tree(client):
    response = await client.get("/api/v1/catalog/categories/tree")

    assert response.status_code == 200
    tree = response.json()
    assert isinstance(tree, list)
    if tree:
        assert "id" in tree[0]
        assert "children" in tree[0]

async def test_catalog_invalid_limit(client):
    response = await client.get(
        "/api/v1/catalog/products",
        params={"limit": 9999},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "VALIDATION_ERROR"
    assert "message" in data


async def test_catalog_invalid_uuid(client):
    response = await client.get("/api/v1/catalog/products/not-a-uuid")
    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "VALIDATION_ERROR"
    assert "message" in data


async def test_b2b_unavailable_returns_502(client):
    from services import b2b as b2b_module

    original_request = b2b_module._b2b_client._client.request

    async def raise_connection_error(*args, **kwargs):
        raise httpx.ConnectError("B2B недоступен")

    with patch.object(b2b_module._b2b_client._client, "request", raise_connection_error):
        response = await client.get("/api/v1/catalog/products")

    assert response.status_code in (502, 503, 504)
    data = response.json()
    assert data["code"] == "B2B_UNAVAILABLE"
    assert "message" in data


async def test_invalid_sort_returns_400(client):
    response = await client.get(
        "/api/v1/catalog/products",
        params={"sort": "invalid_sort_value"},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_REQUEST"
    assert "message" in data
    valid_values = ["popularity", "price_asc", "price_desc", "new"]
    assert any(v in data["message"] for v in valid_values)
