import pytest
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from main import app
from asgi_lifespan import LifespanManager


@pytest.fixture(scope="module")
async def client():
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture(scope="module", autouse=True)
async def require_b2b(client):
    response = await client.get("/api/v1/catalog/products", params={"limit": 1})
    if response.status_code == 502:
        pytest.skip("B2B недоступен")


async def test_product_card_returns_full_data_with_skus(client):
    products = await client.get("/api/v1/catalog/products", params={"limit": 1})
    items = products.json()["items"]

    if not items:
        pytest.skip("Нет товаров в B2B")

    product_id = items[0]["id"]
    response = await client.get(f"/api/v1/catalog/products/{product_id}")

    assert response.status_code == 200
    data = response.json()

    assert "id" in data
    assert data["id"] == product_id
    assert "skus" in data
    assert isinstance(data["skus"], list)
    assert len(data["skus"]) > 0

    sku = data["skus"][0]
    assert "id" in sku
    assert "price" in sku


async def test_cost_price_absent_in_response(client):
    products = await client.get("/api/v1/catalog/products", params={"limit": 1})
    items = products.json()["items"]

    if not items:
        pytest.skip("Нет товаров в B2B")

    product_id = items[0]["id"]
    response = await client.get(f"/api/v1/catalog/products/{product_id}")

    assert response.status_code == 200
    data = response.json()

    assert len(data["skus"]) > 0
    assert "cost_price" not in data["skus"][0], (
        "cost_price не должен быть в публичном ответе"
    )


async def test_blocked_product_returns_404(client):
    fake_id = uuid4()
    response = await client.get(f"/api/v1/catalog/products/{fake_id}")

    assert response.status_code == 404
    assert "detail" in response.json()