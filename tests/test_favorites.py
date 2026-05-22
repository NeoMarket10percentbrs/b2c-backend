# tests/test_favorites.py
import pytest
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete
from main import app
from asgi_lifespan import LifespanManager
from core.security import create_access_token, hash_password
from core.database import get_db
from models.favorite import Favorite
from models.buyer import Buyer


@pytest.fixture(scope="module")
async def client():
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture(scope="module")
async def auth_buyer():
    buyer_id = uuid4()
    async for db in get_db():
        buyer = Buyer(
            id=buyer_id,
            email=f"test_{uuid4().hex[:8]}@example.com",
            password_hash=hash_password("testpass123"),
            first_name="Test",
            last_name="User",
            is_active=True,
        )
        db.add(buyer)
        await db.commit()
        await db.refresh(buyer)
        token = create_access_token(str(buyer.id))
        break

    yield buyer, token

    async for db in get_db():
        await db.execute(delete(Favorite).where(Favorite.buyer_id == buyer_id))
        await db.execute(delete(Buyer).where(Buyer.id == buyer_id))
        await db.commit()
        break


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


async def test_add_to_favorites_returns_201(client, auth_buyer, existing_product_id):
    buyer, token = auth_buyer
    response = await client.put(
        f"/api/v1/favorites/{existing_product_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201


async def test_repeat_add_returns_201_not_duplicate(client, auth_buyer, existing_product_id):
    buyer, token = auth_buyer

    response = await client.put(
        f"/api/v1/favorites/{existing_product_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    async for db in get_db():
        result = await db.execute(
            select(Favorite).where(
                Favorite.buyer_id == buyer.id,
                Favorite.product_id == existing_product_id,
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1, f"Ожидалась 1 запись, найдено {len(rows)}"
        break


async def test_blocked_product_excluded_from_list(client, auth_buyer):
    buyer, token = auth_buyer
    fake_product_id = uuid4()

    async for db in get_db():
        fav = Favorite(buyer_id=buyer.id, product_id=fake_product_id)
        db.add(fav)
        await db.commit()
        break

    try:
        response = await client.get(
            "/api/v1/favorites",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()["items"]]
        assert str(fake_product_id) not in ids
    finally:
        async for db in get_db():
            await db.execute(
                delete(Favorite).where(
                    Favorite.buyer_id == buyer.id,
                    Favorite.product_id == fake_product_id,
                )
            )
            await db.commit()
            break


async def test_user_id_from_query_is_ignored(client, auth_buyer):
    buyer, token = auth_buyer

    response = await client.get(
        "/api/v1/favorites",
        params={"user_id": str(uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total_count" in data
    assert isinstance(data["items"], list)


async def test_favorites_invalid_limit_returns_422(client, auth_buyer):
    _, token = auth_buyer
    response = await client.get(
        "/api/v1/favorites",
        params={"limit": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "VALIDATION_ERROR"
    assert "message" in data