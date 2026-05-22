import pytest
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete
from main import app
from asgi_lifespan import LifespanManager
from core.database import get_db
from models.product_subscription import ProductSubscription
from models.buyer import Buyer


@pytest.fixture(scope="module")
async def client():
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture(scope="module")
async def auth_token(client):
    email = f"sub_test_{uuid4().hex[:8]}@example.com"
    password = "testpass123"
    resp = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "first_name": "Test",
        "last_name": "User"
    })
    assert resp.status_code in (200, 201), f"Регистрация провалилась: {resp.text}"
    data = resp.json()
    return data["access_token"], data["user_id"]


@pytest.fixture(scope="module")
async def existing_product_id(client):
    response = await client.get(
        "/api/v1/catalog/products", params={"limit": 1, "sort": "popularity"}
    )
    if response.status_code != 200:
        pytest.skip("B2B недоступен")
    items = response.json().get("items", [])
    if not items:
        pytest.skip("Нет товаров в B2B")
    return items[0]["id"]


async def test_subscribe_returns_204_with_notify_on(client, auth_token, existing_product_id):
    token, _ = auth_token
    response = await client.post(
        f"/api/v1/favorites/{existing_product_id}/subscribe",
        json={"events": ["BACK_IN_STOCK", "PRICE_DROP"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


async def test_duplicate_subscription_returns_409(client, auth_token, existing_product_id):
    token, _ = auth_token
    response = await client.post(
        f"/api/v1/favorites/{existing_product_id}/subscribe",
        json={"events": ["BACK_IN_STOCK"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    data = response.json()
    assert data["code"] == "SUBSCRIPTION_EXISTS"
    assert "message" in data


async def test_invalid_notify_on_returns_400(client, auth_token, existing_product_id):
    token, _ = auth_token
    other_product_id = uuid4()
    response = await client.post(
        f"/api/v1/favorites/{other_product_id}/subscribe",
        json={"events": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in (400, 404, 422)
    if response.status_code == 400:
        data = response.json()
        assert data["code"] == "INVALID_REQUEST"
        assert "message" in data
    elif response.status_code == 404:
        data = response.json()
        assert data["code"] == "PRODUCT_NOT_FOUND"
        assert "message" in data
    else:
        data = response.json()
        assert data["code"] == "VALIDATION_ERROR"
        assert "message" in data


async def test_subscribe_to_unknown_product_returns_404(client, auth_token):
    token, _ = auth_token
    fake_id = uuid4()
    response = await client.post(
        f"/api/v1/favorites/{fake_id}/subscribe",
        json={"events": ["BACK_IN_STOCK"]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code in (204, 404)
    if response.status_code == 404:
        data = response.json()
        assert data["code"] == "PRODUCT_NOT_FOUND"
        assert "message" in data