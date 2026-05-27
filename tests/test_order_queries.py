import pytest
from uuid import uuid4, UUID
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from main import app
from core.database import AsyncSessionLocal, Base, engine
from core.security import create_access_token, hash_password
from models.buyer import Buyer
from models.address import Address
from models.payment_method import PaymentMethod
from models.order import Order, OrderStatus
from models.order_item import OrderItem
from services.b2b import init_b2b_client, close_b2b_client

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(scope="session", autouse=True)
async def manage_b2b_client():
    init_b2b_client()
    yield
    await close_b2b_client()

@pytest.fixture(scope="session", autouse=True)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# Users
@pytest.fixture
async def buyer1(db_session):
    b = Buyer(
        id=uuid4(),
        email=f"buyer1_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass"),
        first_name="Alice",
        last_name="Test",
        is_active=True,
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest.fixture
async def buyer2(db_session):
    b = Buyer(
        id=uuid4(),
        email=f"buyer2_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass"),
        first_name="Bob",
        last_name="Test",
        is_active=True,
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest.fixture
def buyer1_token(buyer1):
    return create_access_token(str(buyer1.id))


@pytest.fixture
def buyer2_token(buyer2):
    return create_access_token(str(buyer2.id))


# Shared resources
@pytest.fixture
async def address(db_session, buyer1):
    addr = Address(
        id=uuid4(),
        buyer_id=buyer1.id,
        country="RU",
        label="Home",
        city="Moscow",
        street="Tverskaya",
        building="1",
        apartment="10",
        postal_code="123456",
        region="Moscow",
        recipient_name="Test User",
        recipient_phone="+71234567890",
    )
    db_session.add(addr)
    await db_session.commit()
    await db_session.refresh(addr)
    return addr


@pytest.fixture
async def payment_method(db_session, buyer1):
    pm = PaymentMethod(
        id=uuid4(),
        buyer_id=buyer1.id,
        type="CARD",
        card_last4="4242",
        card_brand="VISA",
    )
    db_session.add(pm)
    await db_session.commit()
    await db_session.refresh(pm)
    return pm


#  Helper 
async def _create_order(
    db_session, buyer_id, address_id,
    payment_method_id,status=OrderStatus.PAID, items_data=None
):
    """Create an order directly in DB with optional custom items."""
    order_id = uuid4()
    order = Order(
        id=order_id,
        idempotency_key=uuid4(),
        idempotency_body_hash="abc",
        buyer_id=buyer_id,
        address_id=address_id,
        payment_method_id=payment_method_id,
        status=status,
        subtotal=1000,
        delivery_cost=0,
        total=1000,
        comment="test",
        reserved_at=datetime.now(timezone.utc),
        paid_at=datetime.now(timezone.utc) if status == OrderStatus.PAID else None,
    )
    db_session.add(order)

    if items_data is None:
        items_data = [
            {
                "sku_id": uuid4(),
                "product_id": uuid4(),
                "name": "Test Item",
                "seller_id": uuid4(),
                "sku_code": "TST",
                "unit_price": 1000,
                "line_total": 1000,
                "quantity": 1,
            }
        ]
    for kwargs in items_data:
        item = OrderItem(order_id=order.id, **kwargs)
        db_session.add(item)

    await db_session.commit()
    await db_session.refresh(order)
    return order


#  Tests 
async def test_orders_list_returns_own_orders_paginated(
    client, db_session, buyer1, buyer1_token, address, payment_method, buyer2
):
    order_ids_buyer1 = []
    for _ in range(3):
        order = await _create_order(db_session, buyer1.id, address.id, payment_method.id)
        order_ids_buyer1.append(order.id)

    addr2 = Address(
        id=uuid4(), buyer_id=buyer2.id, country="RU", label="Home",
        city="Moscow", street="Tverskaya", building="1", apartment="10",
        postal_code="123456", region="Moscow",
        recipient_name="Test", recipient_phone="+71234567890",
    )
    pm2 = PaymentMethod(
        id=uuid4(), buyer_id=buyer2.id, type="CARD",
        card_last4="4242", card_brand="VISA",
    )
    db_session.add_all([addr2, pm2])
    await db_session.commit()

    await _create_order(db_session, buyer2.id, addr2.id, pm2.id)

    headers = {"Authorization": f"Bearer {buyer1_token}"}

    resp = await client.get("/api/v1/orders?limit=2&offset=0", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 3
    assert len(data["items"]) == 2
    returned_ids = [UUID(item["id"]) for item in data["items"]]
    assert set(returned_ids).issubset(order_ids_buyer1)

    resp2 = await client.get("/api/v1/orders?limit=2&offset=2", headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["items"]) == 1
    assert UUID(data2["items"][0]["id"]) in order_ids_buyer1


async def test_order_detail_shows_fixed_prices(
    client, db_session, buyer1, buyer1_token, address, payment_method
):
    items_data = [
        {
            "sku_id": uuid4(),
            "product_id": uuid4(),
            "name": "Test Item",
            "seller_id": uuid4(),
            "sku_code": "TST",
            "unit_price": 1500,
            "line_total": 3000,
            "quantity": 2,
        }
    ]
    order = await _create_order(
        db_session, buyer1.id, address.id,
        payment_method.id, items_data=items_data
    )
    headers = {"Authorization": f"Bearer {buyer1_token}"}
    resp = await client.get(f"/api/v1/orders/{order.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["unit_price"] == 1500
    assert item["quantity"] == 2
    assert item["line_total"] == 3000


async def test_other_user_order_returns_404(
    client, db_session, buyer1, buyer2, buyer1_token, buyer2_token, address, payment_method
):
    order = await _create_order(db_session, buyer1.id, address.id, payment_method.id)
    headers = {"Authorization": f"Bearer {buyer2_token}"}
    resp = await client.get(f"/api/v1/orders/{order.id}", headers=headers)
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "ORDER_NOT_FOUND"
    assert "message" in data