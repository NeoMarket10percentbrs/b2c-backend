from __future__ import annotations
from typing import Any
from uuid import UUID
import httpx
from fastapi import HTTPException, status
from core.config import settings


class B2BClientError(HTTPException):
    pass


class B2BNotFoundError(B2BClientError):
    pass


class B2BConflictError(B2BClientError):
    pass


class B2BClient:
    def __init__(self, base_url: str, internal_token: str, timeout: float) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"User-Agent": "NeoMarket-B2C/1.0"},
        )
        self._internal_headers = {"X-Internal-Token": internal_token}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, *,
        params: dict[str, Any] | None = None,
        json: Any = None, internal: bool = False) -> Any:
        
        headers = self._internal_headers if internal else None
        try:
            response = await self._client.request(
                method, path, params=params, json=json, headers=headers
            )
        except httpx.TimeoutException as exc:
            raise B2BClientError(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"B2B сервис не ответил вовремя: {exc}",
            ) from exc
        except httpx.HTTPError as exc:
            raise B2BClientError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Ошибка связи с B2B сервисом: {exc}",
            ) from exc

        if response.status_code == 404:
            raise B2BNotFoundError(
                status_code=status.HTTP_404_NOT_FOUND, detail="Ресурс не найден в B2B"
            )
        if response.status_code == 409:
            raise B2BConflictError(
                status_code=status.HTTP_409_CONFLICT,
                detail=_safe_detail(response, "Конфликт в B2B"),
            )
        if response.status_code >= 400:
            raise B2BClientError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=_safe_detail(response, f"B2B вернул {response.status_code}"),
            )

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    async def list_products(
        self, *, category_id: UUID | None = None,
        search: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        seller_id: UUID | None = None,
        page: int = 1, size: int = 20) -> dict:
        params: dict[str, Any] = {"page": page, "size": size}
        if category_id:
            params["category_id"] = str(category_id)
        if search:
            params["search"] = search
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        if seller_id:
            params["seller_id"] = str(seller_id)
        return await self._request("GET", "/api/public/products", params=params)

    async def get_product(self, product_id: UUID) -> dict:
        return await self._request("GET", f"/api/public/products/{product_id}")

    async def get_similar_products(self, product_id: UUID, limit: int = 10) -> list[dict]:
        data = await self._request(
            "GET", f"/api/public/products/{product_id}/similar", params={"limit": limit}
        )
        return data or []

    async def get_sku(self, sku_id: UUID) -> dict:
        return await self._request("GET", f"/api/public/skus/{sku_id}")

    async def get_skus_bulk(self, sku_ids: list[UUID]) -> dict[UUID, dict]:
        if not sku_ids:
            return {}
        data = await self._request(
            "POST", "/api/skus/bulk",
            json={"ids": [str(sid) for sid in sku_ids]},
        )
        result: dict[UUID, dict] = {}
        for entry in data or []:
            try:
                result[UUID(entry["id"])] = entry
            except (KeyError, ValueError):
                continue
        return result

    async def get_products_bulk(self, product_ids: list[UUID]) -> dict[UUID, dict]:
        if not product_ids:
            return {}
        data = await self._request(
            "POST", "/api/products/bulk",
            json={"ids": [str(pid) for pid in product_ids]},
        )
        result: dict[UUID, dict] = {}
        for entry in data or []:
            try:
                result[UUID(entry["id"])] = entry
            except (KeyError, ValueError):
                continue
        return result

    async def get_categories_tree(self) -> list[dict]:
        data = await self._request("GET", "/api/public/categories/tree")
        return data or []

    async def get_breadcrumbs(self, category_id: UUID) -> list[dict]:
        data = await self._request(
            "GET", f"/api/public/categories/{category_id}/breadcrumbs"
        )
        return data or []

    async def reserve_stock(self, order_id: UUID, items: list[dict[str, Any]]) -> None:
        """items: [{sku_id: str, quantity: int}, ...]"""
        await self._request(
            "POST", f"/api/stock/reserve/{order_id}",
            json=items,
            internal=True,
        )

    async def release_reservation(self, order_id: UUID) -> None:
        await self._request(
            "POST", f"/api/stock/reserve/{order_id}/release", internal=True
        )

    async def commit_reservation(self, order_id: UUID) -> None:
        await self._request(
            "POST", f"/api/stock/reserve/{order_id}/commit", internal=True
        )


def _safe_detail(response: httpx.Response, fallback: str) -> str:
    try:
        data = response.json()
        if isinstance(data, dict) and "detail" in data:
            return str(data["detail"])
    except ValueError:
        pass
    return fallback


_b2b_client: B2BClient | None = None


def init_b2b_client() -> B2BClient:
    print(settings.B2B_BASE_URL)
    global _b2b_client
    _b2b_client = B2BClient(
        base_url=settings.B2B_BASE_URL,
        internal_token=settings.B2B_INTERNAL_TOKEN,
        timeout=settings.B2B_TIMEOUT_SECONDS,
    )
    return _b2b_client


async def close_b2b_client() -> None:
    global _b2b_client
    if _b2b_client is not None:
        await _b2b_client.aclose()
        _b2b_client = None


def get_b2b_client() -> B2BClient:
    if _b2b_client is None:
        raise RuntimeError("B2B клиент не инициализирован")
    return _b2b_client
