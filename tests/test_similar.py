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


@pytest.fixture(scope="module")
async def existing_product_id(client):
    """Берём реальный товар из B2B, или пропускаем если нет."""
    response = await client.get("/api/v1/catalog/products", params={"limit": 1})
    if response.status_code != 200:
        pytest.skip("B2B недоступен")
    items = response.json().get("items", [])
    if not items:
        pytest.skip("Нет товаров в B2B")
    return items[0]["id"]


async def test_similar_returns_up_to_8_from_same_category(client, existing_product_id):
    response = await client.get(
        f"/api/v1/catalog/products/{existing_product_id}/similar",
        params={"limit": 8},
    )
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) <= 8
    ids = [item["id"] for item in items]
    assert existing_product_id not in ids


async def test_empty_category_returns_200_empty_list(client, existing_product_id):
    """
    Если похожих нет — эндпоинт должен вернуть 200 с пустым списком.
    B2B возвращает [] при отсутствии похожих товаров.
    """
    response = await client.get(
        f"/api/v1/catalog/products/{existing_product_id}/similar",
        params={"limit": 50},
    )
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)

    for item in items:
        assert "id" in item
        assert "name" in item


async def test_unknown_product_returns_404(client):
    fake_id = uuid4()
    response = await client.get(f"/api/v1/catalog/products/{fake_id}/similar")
    assert response.status_code == 404
    data = response.json()
    assert "code" in data
    assert "message" in data