# tests/test_order.py

import asyncio
import pytest
from uuid import uuid4, UUID
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from sqlalchemy import delete
from core.config import settings
from core.database import AsyncSessionLocal, Base, engine
from core.security import hash_password, create_access_token
from main import app
from models.buyer import Buyer
from models.address import Address
from models.payment_method import PaymentMethod
from models.cart import Cart
from models.cart_item import CartItem
from models.order import Order
from models.order_item import OrderItem
from services.b2b import init_b2b_client, close_b2b_client, B2BClient

pytestmark = pytest.mark.asyncio(loop_scope="session")

# ---------- инициализация БД и B2B ----------
@pytest.fixture(scope="session", autouse=True)
async def init_db():
    # Подготавливаем БД
    for _ in range(10):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            break
        except Exception:
            await asyncio.sleep(1)

    # Настраиваем B2B‑клиент на реальный сервис (из вашего .env)
    settings.B2B_BASE_URL = "http://localhost:8000"
    settings.B2C_SERVICE_KEY = "67277c5e88976543b83"   # реальный ключ!

    init_b2b_client()
    yield
    await close_b2b_client()
    await engine.dispose()

@pytest.fixture(scope="module")
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session

@pytest.fixture(scope="module")
async def buyer_token(db_session):
    buyer_id = uuid4()
    buyer = Buyer(
        id=buyer_id,
        email=f"buyer-{uuid4()}@example.com",
        password_hash=hash_password("testpass123"),
        first_name="Test",
        last_name="Buyer",
        is_active=True,
    )
    db_session.add(buyer)
    await db_session.commit()
    await db_session.refresh(buyer)
    token = create_access_token(str(buyer.id))
    yield token, str(buyer.id)

    await db_session.execute(delete(OrderItem))
    await db_session.execute(delete(Order))
    await db_session.execute(delete(CartItem))
    await db_session.execute(delete(Cart))
    await db_session.execute(delete(Address))
    await db_session.execute(delete(PaymentMethod))
    await db_session.execute(delete(Buyer).where(Buyer.id == buyer_id))
    await db_session.commit()

@pytest.fixture(scope="module")
async def client(buyer_token):
    transport = ASGITransport(app=app)
    token, _ = buyer_token
    async with AsyncClient(
        transport=transport, base_url="http://test",
        headers={"Authorization": f"Bearer {token}"}
    ) as ac:
        yield ac

@pytest.fixture(scope="module")
async def real_sku(client):
    resp = await client.get(
        "/api/v1/catalog/products",
        params={"limit": 1, "sort": "popularity"}
    )
    if resp.status_code != 200 or not resp.json().get("items"):
        pytest.skip("Нет товаров в B2B каталоге")
    product_id = resp.json()["items"][0]["id"]
    detail = await client.get(f"/api/v1/catalog/products/{product_id}")
    if detail.status_code != 200:
        pytest.skip("Не удалось получить детали товара")
    skus = detail.json().get("skus", [])
    if not skus:
        pytest.skip("У товара нет SKU")
    for sku in skus:
        if sku.get("available_quantity", 0) > 0:
            return sku
    pytest.skip("Нет SKU с положительным остатком")

# Заголовки для прямых вызовов B2B‑сервиса (inventory)
@pytest.fixture
def b2b_headers():
    return {"X-Service-Key": "67277c5e88976543b83"}

async def _create_address(db_session, buyer_id: UUID) -> Address:
    address = Address(
        id=uuid4(), buyer_id=buyer_id, country="RU", label="Home",
        city="Moscow", street="Tverskaya", building="1", apartment="10",
        postal_code="123456", region="Moscow",
        recipient_name="Test User", recipient_phone="+71234567890",
    )
    db_session.add(address)
    await db_session.commit()
    await db_session.refresh(address)
    return address

async def _create_payment_method(db_session, buyer_id: UUID) -> PaymentMethod:
    pm = PaymentMethod(
        id=uuid4(), buyer_id=buyer_id, type="CARD",
        card_last4="4242", card_brand="VISA",
    )
    db_session.add(pm)
    await db_session.commit()
    await db_session.refresh(pm)
    return pm

async def _fill_cart_via_api(client, sku_id: str, quantity: int):
    resp = await client.post(
        "/api/v1/cart/items",
        json={"sku_id": sku_id, "quantity": quantity},
    )
    assert resp.status_code == 200

# ============================================================
async def test_checkout_creates_paid_order_with_fixed_prices(
    client, db_session, buyer_token, real_sku
):
    await client.delete("/api/v1/cart")
    _, buyer_id = buyer_token
    sku_id = real_sku["id"]
    sku_price = real_sku["price"]

    address = await _create_address(db_session, UUID(buyer_id))
    payment_method = await _create_payment_method(db_session, UUID(buyer_id))
    await _fill_cart_via_api(client, sku_id, 2)

    idempotency_key = str(uuid4())
    resp = await client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": idempotency_key},
        json={
            "address_id": str(address.id),
            "payment_method_id": str(payment_method.id),
            "comment": "Test order",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "PAID"
    items = data["items"]
    assert len(items) == 1
    item = items[0]
    assert item["unit_price"] == sku_price
    assert item["quantity"] == 2
    assert item["sku_id"] == sku_id

# ============================================================
async def test_partial_reserve_failure_returns_409(
    client, db_session, buyer_token, real_sku, b2b_headers
):
    await client.delete("/api/v1/cart")
    _, buyer_id = buyer_token
    sku_id = real_sku["id"]
    available = real_sku.get("available_quantity", 1)
    await _fill_cart_via_api(client, sku_id, available)

    # Резервируем 1 единицу напрямую через B2B‑сервис
    reserve_key = str(uuid4())
    async with AsyncClient(base_url="http://localhost:8000") as b2b_client:
        reserve_resp = await b2b_client.post(
            "/api/v1/inventory/reserve",
            headers=b2b_headers,
            json={
                "idempotency_key": reserve_key,
                "order_id": str(uuid4()),
                "items": [{"sku_id": sku_id, "quantity": 1}],
            },
        )
    assert reserve_resp.status_code == 200, f"Не удалось зарезервировать: {reserve_resp.text}"

    address = await _create_address(db_session, UUID(buyer_id))
    payment_method = await _create_payment_method(db_session, UUID(buyer_id))
    resp = await client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "address_id": str(address.id),
            "payment_method_id": str(payment_method.id),
        },
    )
    assert resp.status_code == 409
    data = resp.json()
    assert "code" in data and "message" in data
    if "details" in data and isinstance(data["details"], dict):
        assert "failed_items" in data["details"]

    # Возвращаем резерв обратно
    async with AsyncClient(base_url="http://localhost:8000") as b2b_client:
        unreserve_resp = await b2b_client.post(
            "/api/v1/inventory/unreserve",
            headers=b2b_headers,
            json={"order_id": reserve_key, "items": [{"sku_id": sku_id, "quantity": 1}]},
        )
    assert unreserve_resp.status_code == 200

# ============================================================
async def test_idempotency_returns_existing_order(
    client, db_session, buyer_token, real_sku
):
    await client.delete("/api/v1/cart")
    _, buyer_id = buyer_token
    sku_id = real_sku["id"]

    address = await _create_address(db_session, UUID(buyer_id))
    payment_method = await _create_payment_method(db_session, UUID(buyer_id))
    await _fill_cart_via_api(client, sku_id, 1)

    idempotency_key = str(uuid4())
    body = {"address_id": str(address.id), "payment_method_id": str(payment_method.id)}

    resp1 = await client.post("/api/v1/orders", headers={"Idempotency-Key": idempotency_key}, json=body)
    assert resp1.status_code == 201
    order1 = resp1.json()

    resp2 = await client.post("/api/v1/orders", headers={"Idempotency-Key": idempotency_key}, json=body)
    assert resp2.status_code == 201
    order2 = resp2.json()
    assert order2["id"] == order1["id"]

# ============================================================
async def test_b2b_unavailable_returns_503(client, db_session, buyer_token, real_sku):
    await client.delete("/api/v1/cart")
    _, buyer_id = buyer_token
    sku_id = real_sku["id"]

    address = await _create_address(db_session, UUID(buyer_id))
    payment_method = await _create_payment_method(db_session, UUID(buyer_id))
    await _fill_cart_via_api(client, sku_id, 1)

    # Создаём клиент с неверным URL
    bad_client = B2BClient(
        base_url="http://localhost:19999",
        service_key=settings.B2C_SERVICE_KEY,
        timeout=0.5,
    )
    with patch("routers.orders.orders_router.get_b2b_client", return_value=bad_client):
        resp = await client.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": str(uuid4())},
            json={"address_id": str(address.id), "payment_method_id": str(payment_method.id)},
        )
    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"