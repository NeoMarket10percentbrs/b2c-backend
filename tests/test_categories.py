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


async def test_category_tree_returns_nested_structure(client):
    response = await client.get("/api/v1/catalog/categories/tree")
    assert response.status_code == 200
    tree = response.json()
    assert isinstance(tree, list)

    def check_node(node: dict, depth: int = 0):
        assert "id" in node, f"Нет поля id на уровне {depth}"
        assert "name" in node, f"Нет поля name на уровне {depth}"
        assert "children" in node, f"Нет поля children на уровне {depth}"
        assert isinstance(node["children"], list)
        for child in node["children"]:
            check_node(child, depth + 1)

    for root in tree:
        check_node(root)


async def test_breadcrumbs_return_path_from_root(client):
    tree_resp = await client.get("/api/v1/catalog/categories/tree")
    if tree_resp.status_code != 200 or not tree_resp.json():
        pytest.skip("Нет категорий в B2B")

    def find_leaf(nodes: list) -> dict | None:
        for node in nodes:
            if node["children"]:
                leaf = find_leaf(node["children"])
                if leaf:
                    return leaf
            else:
                return node
        return nodes[0] if nodes else None

    leaf = find_leaf(tree_resp.json())
    if not leaf:
        pytest.skip("Нет листовых категорий")

    response = await client.get(f"/api/v1/catalog/categories/{leaf['id']}/breadcrumbs")
    if response.status_code in (404, 502):
        pytest.skip("Breadcrumbs не реализованы в B2B")

    assert response.status_code == 200
    crumbs = response.json()
    assert isinstance(crumbs, list)
    assert len(crumbs) >= 1
    assert crumbs[-1]["id"] == leaf["id"]
    for i in range(1, len(crumbs)):
        assert crumbs[i].get("parent_id") == crumbs[i - 1]["id"]


async def test_ambiguous_params_returns_400(client):
    response = await client.get(
        "/api/v1/catalog/products",
        params={"q": "а", "filter[category_id]": str(uuid4())},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_REQUEST"
    assert "message" in data


async def test_orphan_node_returns_422(client):
    response = await client.get(
        "/api/v1/catalog/products",
        params={"filter[category_id]": "not-a-valid-uuid"},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "VALIDATION_ERROR"
    assert "message" in data