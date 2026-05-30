import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from asgi_lifespan import LifespanManager


@pytest.fixture(scope="module")
async def client():
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


async def test_search_returns_matching_products(client):
    response = await client.get(
        "/api/v1/catalog/products",
        params={"q": "тел"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total_count" in data
    assert isinstance(data["items"], list)


async def test_short_query_returns_400(client):
    for short_q in ["а", "ab", " а"]:
        response = await client.get(
            "/api/v1/catalog/products",
            params={"q": short_q},
        )
        assert response.status_code == 400, f"Ожидался 400 для q='{short_q}'"
        data = response.json()
        assert data["code"] == "INVALID_REQUEST"
        assert "message" in data


async def test_special_chars_do_not_break_query(client):
    for special_q in ["100%", "a_b_c", "it's"]:
        response = await client.get(
            "/api/v1/catalog/products",
            params={"q": special_q},
        )
        assert response.status_code in (200, 400), (
            f"Неожиданный статус {response.status_code} для q='{special_q}'"
        )
        data = response.json()
        if response.status_code == 200:
            assert "items" in data
            assert isinstance(data["items"], list)
        else:
            assert data["code"] == "INVALID_REQUEST"
            assert "message" in data


async def test_empty_results_returns_200(client):
    response = await client.get(
        "/api/v1/catalog/products",
        params={"q": "xzqwerty_несуществующий_товар_12345"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["total_count"] == 0
    assert data["items"] == []


async def test_search_inside_category(client):
    cats = await client.get("/api/v1/catalog/categories")
    cat = cats.json()[0]
    
    resp = await client.get("/api/v1/catalog/products", params={
        "q": "тел",
        "filter[category_id]": cat["id"]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["items"], list)