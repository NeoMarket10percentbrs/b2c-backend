from __future__ import annotations
from typing import Any
from uuid import UUID
import httpx
from fastapi import HTTPException, status
from core.config import settings

VALID_SORT_VALUES = {"popularity", "price_asc", "price_desc", "new"}


def _error_detail(code: str, message: str) -> dict:
    return {"code": code, "message": message}

class B2BClientError(HTTPException):
    pass


class B2BNotFoundError(B2BClientError):
    pass


class B2BConflictError(B2BClientError):
    pass


class B2BClient:
    def __init__(self, base_url: str, service_key: str, timeout: float) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"User-Agent": "NeoMarket-B2C/1.0"},
        )
        self._service_headers = {"X-Service-Key": service_key}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        try:
            response = await self._client.request(
                method, path, params=params, json=json, headers=headers
            )
        except httpx.TimeoutException as exc:
            raise B2BClientError(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=_error_detail("B2B_TIMEOUT", f"B2B service did not respond in time: {exc}"),
            ) from exc
        except httpx.HTTPError as exc:
            raise B2BClientError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=_error_detail("B2B_UNAVAILABLE", f"Failed to reach B2B service: {exc}"),
            ) from exc

        if response.status_code == 404:
            raise B2BNotFoundError(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_error_detail("B2B_NOT_FOUND", "Resource not found in B2B"),
            )
        if response.status_code == 409:
            data = _safe_json(response)
            message = data if isinstance(data, str) else _safe_detail(response, "Conflict in B2B")
            raise B2BConflictError(
                status_code=status.HTTP_409_CONFLICT,
                detail=_error_detail("B2B_CONFLICT", str(message)),
            )
        if response.status_code >= 400:
            raise B2BClientError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=_error_detail(
                    "B2B_ERROR",
                    _safe_detail(response, f"B2B returned {response.status_code}"),
                ),
            )

        return _safe_json(response)

    async def list_products(
        self, *, category_id: UUID | None = None,
        search: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        limit: int = 20, offset: int = 0,
        sort: str | None = None,
    ) -> dict:
            
        if sort not in VALID_SORT_VALUES:
            raise HTTPException(
                status_code=400,
                detail=_error_detail(
                    "INVALID_REQUEST",
                    f"Invalid sort value '{sort}'. Allowed: {', '.join(sorted(VALID_SORT_VALUES))}",
                ),
            )
        
        if search is not None and len(search.strip()) < 3:
            raise HTTPException(
                status_code=400,
                detail=_error_detail(
                    "INVALID_REQUEST",
                    "Search query must be at least 3 characters",
                ),
            )
                
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if category_id:
            params["filter[category_id]"] = str(category_id)
        if search:
            params["search"] = search
        if min_price is not None:
            params["filter[price_min]"] = min_price
        if max_price is not None:
            params["filter[price_max]"] = max_price
        if sort:
            params["sort"] = sort
        return await self._request("GET", "/api/v1/public/products", params=params, headers=self._service_headers)

    async def get_product(self, product_id: UUID) -> dict:
        return await self._request("GET", f"/api/v1/public/products/{product_id}", headers=self._service_headers)

    async def get_similar_products(self, product_id: UUID, limit: int = 10) -> list[dict]:
        data = await self._request(
            "GET", f"/api/v1/public/products/{product_id}/similar", params={"limit": limit}, headers=self._service_headers
        )
        return data or []

    async def get_sku(self, sku_id: UUID) -> dict:
        return await self._request("GET", f"/api/v1/public/skus/{sku_id}", headers=self._service_headers)

    async def get_products_by_ids(self, product_ids: list[UUID]) -> dict[UUID, dict]:
        if not product_ids:
            return {}
        payload = {"product_ids": [str(pid) for pid in product_ids]}
        data = await self._request(
            "POST", "/api/v1/public/products/batch", json=payload, headers=self._service_headers
        )
        # data – это list[dict] с товарами
        result: dict[UUID, dict] = {}
        for entry in data or []:
            try:
                result[UUID(entry["id"])] = entry
            except (KeyError, ValueError):
                continue
        return result

    async def get_categories_tree(self) -> list[dict]:
        data = await self._request("GET", "/api/v1/categories/tree", headers=self._service_headers)
        return data or []

    async def get_categories(self) -> list[dict]:
        data = await self._request("GET", "/api/v1/categories", headers=self._service_headers)
        return data or []

    async def get_breadcrumbs(self, category_id: UUID) -> list[dict]:
        data = await self._request(
            "GET", f"/api/v1/categories/{category_id}/breadcrumbs", headers=self._service_headers
        )
        return data or []

    async def get_banners(self) -> list[dict]:
        data = await self._request("GET", "/api/public/banners", headers=self._service_headers)
        return data or []

    async def get_collections(self) -> list[dict]:
        data = await self._request("GET", "/api/collections", headers=self._service_headers)
        return data or []

    async def reserve(self, idempotency_key: UUID, items: list[dict[str, Any]]) -> dict:
        """items: [{sku_id: str, quantity: int}, ...]"""
        data = await self._request(
            "POST", "/api/v1/reserve",
            json={"idempotency_key": str(idempotency_key), "items": items},
            headers=self._service_headers,
        )
        return data or {"reserved": True, "items": []}

    async def unreserve(self, order_id: UUID, items: list[dict[str, Any]]) -> Any:
        return await self._request(
            "POST", "/api/v1/unreserve",
            json={"order_id": str(order_id), "items": items},
            headers=self._service_headers,
        )

    async def fulfill(self, order_id: UUID, items: list[dict[str, Any]]) -> Any:
        return await self._request(
            "POST", "/api/v1/fulfill",
            json={"order_id": str(order_id), "items": items},
            headers=self._service_headers,
        )


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _safe_detail(response: httpx.Response, fallback: str) -> str:
    data = _safe_json(response)
    if isinstance(data, dict) and "detail" in data:
        return str(data["detail"])
    return fallback


_b2b_client: B2BClient | None = None


def init_b2b_client() -> B2BClient:
    print(settings.B2B_BASE_URL)
    global _b2b_client
    _b2b_client = B2BClient(
        base_url=settings.B2B_BASE_URL,
        service_key=settings.B2C_SERVICE_KEY,
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
