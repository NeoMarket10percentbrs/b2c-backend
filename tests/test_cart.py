import pytest
from uuid import uuid4, UUID
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete
from main import app
from unittest.mock import patch, AsyncMock
from asgi_lifespan import LifespanManager
from core.config import settings
from core.database import get_db
from models.cart import Cart
from models.cart_item import CartItem as CartItemModel
from services.b2b import B2BClient


@pytest.fixture(scope="module")
async def client():
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture(scope="function")
async def session_id():
    return f"test-session-{uuid4().hex}"


@pytest.fixture(scope="module")
async def auth_token(client):
    email = f"cart_test_{uuid4().hex[:8]}@example.com"
    resp = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "testpass123",
        "first_name": "Test",
        "last_name": "User"
    })
    assert resp.status_code in (200, 201), f"Регистрация провалилась: {resp.text}"
    data = resp.json()
    return data["access_token"], data["user_id"]


@pytest.fixture(scope="module")
async def real_sku(client):
    resp = await client.get("/api/v1/catalog/products", params={"limit": 1, "sort": "popularity"})
    if resp.status_code != 200 or not resp.json().get("items"):
        pytest.skip("Нет товаров в B2B")

    product_id = resp.json()["items"][0]["id"]
    detail = await client.get(f"/api/v1/catalog/products/{product_id}")
    if detail.status_code != 200:
        pytest.skip("Не удалось получить детали товара")

    skus = detail.json().get("skus", [])
    if not skus:
        pytest.skip("У товара нет SKU")
    return skus[0]


async def test_add_sku_increments_quantity_if_already_in_cart(client, session_id, real_sku):
    sku_id = real_sku["id"]
    headers = {"X-Session-Id": session_id}

    await client.delete("/api/v1/cart", headers=headers)

    r1 = await client.post(
        "/api/v1/cart/items",
        json={"sku_id": sku_id, "quantity": 1},
        headers=headers,
    )
    assert r1.status_code == 200
    qty_after_first = next(
        (i["quantity"] for i in r1.json()["items"] if i["sku_id"] == sku_id), None
    )
    assert qty_after_first == 1

    r2 = await client.post(
        "/api/v1/cart/items",
        json={"sku_id": sku_id, "quantity": 2},
        headers=headers,
    )
    assert r2.status_code == 200
    qty_after_second = next(
        (i["quantity"] for i in r2.json()["items"] if i["sku_id"] == sku_id), None
    )
    assert qty_after_second == 3  # 1 + 2


async def test_get_cart_enriched_with_b2b_data(client, session_id, real_sku):
    headers = {"X-Session-Id": session_id}
    
    add_resp = await client.post(
        "/api/v1/cart/items",
        json={"sku_id": real_sku["id"], "quantity": 1},
        headers=headers,
    )
    assert add_resp.status_code == 200

    response = await client.get("/api/v1/cart", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert "id" in data
    assert "items" in data
    assert "items_count" in data
    assert "subtotal" in data
    assert "is_valid" in data
    assert isinstance(data["items"], list)

    items = data["items"]
    assert len(items) > 0
    item = items[0]
    assert "sku_id" in item
    assert "quantity" in item
    assert "is_available" in item


async def test_unavailable_sku_shown_with_reason(client, auth_token):
    token, _ = auth_token
    headers = {"Authorization": f"Bearer {token}"}
    fake_sku_id = uuid4()

    async for db in get_db():
        cart_resp = await client.get("/api/v1/cart", headers=headers)
        cart_id = cart_resp.json()["id"]

        item = CartItemModel(
            cart_id=cart_id,
            sku_id=fake_sku_id,
            product_id=uuid4(),
            quantity=1,
        )
        db.add(item)
        await db.commit()
        break

    response = await client.get("/api/v1/cart", headers=headers)
    assert response.status_code == 200

    items = response.json()["items"]
    unavailable = [i for i in items if i["sku_id"] == str(fake_sku_id)]
    assert len(unavailable) == 1
    assert unavailable[0]["is_available"] is False

    async for db in get_db():
        await db.execute(
            delete(CartItemModel).where(CartItemModel.sku_id == fake_sku_id)
        )
        await db.commit()
        break


async def test_guest_cart_merged_on_login(client, real_sku):
    sku_id = real_sku["id"]
    guest_sid = f"merge-test-{uuid4().hex}"

    email = f"merge_{uuid4().hex[:8]}@example.com"
    reg = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "testpass123", "first_name": "Test", "last_name": "User"
    })
    assert reg.status_code in (200, 201)
    token = reg.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/v1/cart/items",
        json={"sku_id": sku_id, "quantity": 2},
        headers={"X-Session-Id": guest_sid},
    )

    await client.post(
        "/api/v1/cart/items",
        json={"sku_id": sku_id, "quantity": 5},
        headers=auth_headers,
    )

    merge_resp = await client.post(
        "/api/v1/cart/merge",
        headers={**auth_headers, "X-Session-Id": guest_sid},
    )
    assert merge_resp.status_code == 200

    merged_items = merge_resp.json()["items"]
    merged_qty = next(
        (i["quantity"] for i in merged_items if i["sku_id"] == sku_id), None
    )
    assert merged_qty == 5, f"Ожидалось 5 (MAX), получено {merged_qty}"


async def test_update_missing_cart_item_returns_404(client):
    response = await client.patch(
        f"/api/v1/cart/items/{uuid4()}",
        json={"quantity": 1},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "CART_ITEM_NOT_FOUND"
    assert "message" in data


# ---------------- новые тесты валидации корзины (реальные данные + изолированный B2B) ----------------
async def _add_sku_to_cart(client, token, sku_id, quantity=1):
    headers = {"Authorization": f"Bearer {token}"}
    await client.delete("/api/v1/cart", headers=headers)
    resp = await client.post(
        "/api/v1/cart/items", 
        json={"sku_id": sku_id, "quantity": quantity}, 
        headers=headers
    )
    assert resp.status_code == 200

async def test_validate_valid(client, auth_token, real_sku):
    token, _ = auth_token
    await _add_sku_to_cart(client, token, real_sku["id"])
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/v1/cart/validate", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert len(data["issues"]) == 0

async def test_validate_price_changed(client, auth_token, real_sku):
    token, _ = auth_token
    await _add_sku_to_cart(client, token, real_sku["id"])
    new_price = real_sku["price"] + 500
    mock_product = {
        "id": real_sku["product_id"],
        "status": "MODERATED",
        "skus": [{**real_sku, "price": new_price}]
    }
    with patch.object(
        B2BClient,
        "get_products_by_ids",
        AsyncMock(return_value={UUID(real_sku["product_id"]): mock_product})
    ):
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/v1/cart/validate", headers=headers)
    data = resp.json()
    issues = data["issues"]
    price_issue = next((i for i in issues if i["type"] == "PRICE_CHANGED"), None)
    assert price_issue is not None, f"No PRICE_CHANGED, issues: {issues}"
    assert price_issue["old_value"] == real_sku["price"]
    assert price_issue["new_value"] == new_price

async def test_validate_product_blocked(client, auth_token, real_sku):
    token, _ = auth_token
    await _add_sku_to_cart(client, token, real_sku["id"])
    mock_product = {
        "id": real_sku["product_id"],
        "status": "BLOCKED",
        "skus": [real_sku]
    }
    with patch.object(
        B2BClient, 
        "get_products_by_ids", 
        AsyncMock(return_value={UUID(real_sku["product_id"]): mock_product})
    ):
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/v1/cart/validate", headers=headers)
    data = resp.json()
    issues = data["issues"]
    assert any(i["type"] == "PRODUCT_BLOCKED" for i in issues)

async def test_validate_out_of_stock(client, auth_token, real_sku):
    token, _ = auth_token
    await _add_sku_to_cart(client, token, real_sku["id"])
    mock_sku = {**real_sku, "active_quantity": 0}
    mock_product = {
        "id": real_sku["product_id"],
        "status": "MODERATED",
        "skus": [mock_sku]
    }
    with patch.object(
        B2BClient, 
        "get_products_by_ids", 
        AsyncMock(return_value={UUID(real_sku["product_id"]): mock_product})
    ):
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/v1/cart/validate", headers=headers)
    data = resp.json()
    issues = data["issues"]
    assert any(i["type"] == "OUT_OF_STOCK" for i in issues)

async def test_validate_quantity_reduced(client, auth_token, real_sku):
    token, _ = auth_token
    await _add_sku_to_cart(client, token, real_sku["id"], quantity=3)
    mock_sku = {**real_sku, "active_quantity": 1}
    mock_product = {
        "id": real_sku["product_id"],
        "status": "MODERATED",
        "skus": [mock_sku]
    }
    with patch.object(
        B2BClient,
        "get_products_by_ids",
        AsyncMock(return_value={UUID(real_sku["product_id"]): mock_product})
    ):
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/v1/cart/validate", headers=headers)
    data = resp.json()
    issues = data["issues"]
    assert any(i["type"] == "QUANTITY_REDUCED" for i in issues)

async def test_validate_product_deleted(client, auth_token, real_sku):
    token, _ = auth_token
    await _add_sku_to_cart(client, token, real_sku["id"])
    mock_product = {
        "id": real_sku["product_id"],
        "status": "MODERATED",
        "skus": []
    }
    with patch.object(
        B2BClient, 
        "get_products_by_ids", 
        AsyncMock(return_value={UUID(real_sku["product_id"]): mock_product})
        ):
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/v1/cart/validate", headers=headers)
    data = resp.json()
    issues = data["issues"]
    assert any(i["type"] == "PRODUCT_DELETED" for i in issues)