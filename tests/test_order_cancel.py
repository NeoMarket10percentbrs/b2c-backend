# tests/test_order_cancel.py
import pytest
from uuid import uuid4, UUID
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from main import app  # B2C FastAPI app
from core.database import AsyncSessionLocal, Base, engine
from core.security import create_access_token, hash_password
from models.buyer import Buyer
from models.address import Address
from models.payment_method import PaymentMethod
from models.order import Order, OrderStatus
from models.order_item import OrderItem
from services.b2b import B2BClient, B2BClientError
from fastapi import status
from services.b2b import init_b2b_client, close_b2b_client

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------- фикстуры ----------

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

@pytest.fixture
async def buyer1(db_session):
    """Первый покупатель"""
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
    """Второй покупатель (для теста IDOR)"""
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
def buyer_token(buyer1):
    return create_access_token(str(buyer1.id))

@pytest.fixture
def buyer2_token(buyer2):
    return create_access_token(str(buyer2.id))

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

async def _create_order(db_session, buyer_id, address_id, payment_method_id, status=OrderStatus.PAID):
    """Создать заказ в БД B2C напрямую."""
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
    item = OrderItem(
        sku_id=uuid4(),
        product_id=uuid4(),
        name="Test Item",
        seller_id=uuid4(),
        sku_code="TST",
        unit_price=1000,
        line_total=1000,
        quantity=1,
        order_id=order.id,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(order)
    return order


# ---------- тесты ----------
async def test_cancel_paid_order_transitions_to_cancelled(
    client, db_session, buyer_token, address, payment_method, buyer1
):
    order = await _create_order(db_session, buyer1.id, address.id, payment_method.id, OrderStatus.PAID)

    with patch.object(B2BClient, "unreserve", new_callable=AsyncMock) as mock_unreserve:
        mock_unreserve.return_value = None
        headers = {"Authorization": f"Bearer {buyer_token}"}
        resp = await client.post(f"/api/v1/orders/{order.id}/cancel", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "CANCELLED"
        assert data["id"] == str(order.id)

        mock_unreserve.assert_called_once()
        pos_args = mock_unreserve.call_args[0]  # позиционные аргументы
        assert pos_args[0] == order.id          # order_id
        items_arg = pos_args[1]
        assert len(items_arg) == 1
        assert items_arg[0]["quantity"] == 1

    # Проверяем статус в БД
    db_order = await db_session.get(Order, order.id)
    await db_session.refresh(db_order)
    assert db_order.status == OrderStatus.CANCELLED


async def test_unreserve_failure_transitions_to_cancel_pending(
    client, db_session, buyer_token, address, payment_method, buyer1
):
    order = await _create_order(db_session, buyer1.id, address.id, payment_method.id, OrderStatus.PAID)

    with patch.object(B2BClient, "unreserve", new_callable=AsyncMock) as mock_unreserve:
        mock_unreserve.side_effect = B2BClientError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": "Failed to reach B2B"},
        )
        headers = {"Authorization": f"Bearer {buyer_token}"}
        resp = await client.post(f"/api/v1/orders/{order.id}/cancel", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "CANCEL_PENDING"
        assert data["id"] == str(order.id)

        mock_unreserve.assert_called_once()

    # Статус в БД
    db_order = await db_session.get(Order, order.id)
    await db_session.refresh(db_order)
    assert db_order.status == OrderStatus.CANCEL_PENDING


async def test_cancel_assembling_order_returns_409(
    client, db_session, buyer_token, address, payment_method, buyer1
):
    order = await _create_order(db_session, buyer1.id, address.id, payment_method.id, OrderStatus.ASSEMBLING)

    with patch.object(B2BClient, "unreserve", new_callable=AsyncMock) as mock_unreserve:
        headers = {"Authorization": f"Bearer {buyer_token}"}
        resp = await client.post(f"/api/v1/orders/{order.id}/cancel", headers=headers)

        assert resp.status_code == 409
        data = resp.json()
        assert data["code"] == "CANCEL_NOT_ALLOWED"
        assert "message" in data
        mock_unreserve.assert_not_called()

    # Статус не изменился
    db_order = await db_session.get(Order, order.id)
    await db_session.refresh(db_order)
    assert db_order.status == OrderStatus.ASSEMBLING


async def test_other_user_order_returns_404(
    client, db_session, buyer1, buyer2, buyer2_token, address, payment_method
):
    order = await _create_order(db_session, buyer1.id, address.id, payment_method.id, OrderStatus.PAID)

    headers = {"Authorization": f"Bearer {buyer2_token}"}
    resp = await client.post(f"/api/v1/orders/{order.id}/cancel", headers=headers)

    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "ORDER_NOT_FOUND"
    assert "message" in data

    # Статус не изменился
    db_order = await db_session.get(Order, order.id)
    await db_session.refresh(db_order)
    assert db_order.status == OrderStatus.PAID