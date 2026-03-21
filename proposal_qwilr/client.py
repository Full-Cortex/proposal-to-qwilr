"""Qwilr API client for creating and managing proposal pages."""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import httpx

from proposal_qwilr.schemas import (
    QwilrConfig,
    QwilrCreatePageRequest,
    QwilrPageResult,
)

logger = logging.getLogger(__name__)

# Status codes that are safe to retry
_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds


class QwilrAPIError(Exception):
    """Base error for Qwilr API calls."""
    def __init__(self, message: str, status_code: int | None = None, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class QwilrAuthError(QwilrAPIError):
    """Authentication failed (401/403)."""


class QwilrRateLimitError(QwilrAPIError):
    """Rate limited (429)."""


class QwilrClient:
    """HTTP client for the Qwilr REST API."""

    def __init__(self, config: QwilrConfig):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an authenticated request with retry + exponential backoff.

        Retries on transient failures (5xx, timeouts, connection errors).
        Does NOT retry on client errors (4xx) except 429 (rate limit).
        """
        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await client.request(method, path, **kwargs)

                if response.status_code in (401, 403):
                    raise QwilrAuthError(
                        f"Authentication failed: {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text,
                    )

                if response.status_code == 429:
                    # Rate limited — retry with backoff
                    retry_after = float(response.headers.get("Retry-After", _BASE_DELAY * 2))
                    if attempt < _MAX_RETRIES:
                        logger.warning(
                            "Rate limited (attempt %d/%d), retrying in %.1fs",
                            attempt + 1, _MAX_RETRIES + 1, retry_after,
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    raise QwilrRateLimitError(
                        "Rate limited by Qwilr API (retries exhausted)",
                        status_code=429,
                        response_body=response.text,
                    )

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    if attempt < _MAX_RETRIES:
                        delay = _BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                        logger.warning(
                            "Qwilr %d error (attempt %d/%d), retrying in %.1fs",
                            response.status_code, attempt + 1, _MAX_RETRIES + 1, delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise QwilrAPIError(
                        f"Qwilr API error: {response.status_code} (retries exhausted)",
                        status_code=response.status_code,
                        response_body=response.text,
                    )

                if response.status_code >= 400:
                    raise QwilrAPIError(
                        f"Qwilr API error: {response.status_code} - {response.text}",
                        status_code=response.status_code,
                        response_body=response.text,
                    )

                return response.json() if response.text else {}

            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError) as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    delay = _BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "Connection error (attempt %d/%d): %s, retrying in %.1fs",
                        attempt + 1, _MAX_RETRIES + 1, e, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise QwilrAPIError(
                    f"Connection failed after {_MAX_RETRIES + 1} attempts: {e}",
                    status_code=None,
                    response_body=str(e),
                ) from e

        # Should never reach here, but safety net
        raise QwilrAPIError(f"Request failed: {last_error}")

    # --- Page Operations ---

    async def create_page(self, request: QwilrCreatePageRequest) -> QwilrPageResult:
        """Create a new Qwilr page from a template with substitutions."""
        data = await self._request("POST", "/pages", json=request.model_dump())
        logger.info("Created Qwilr page: %s", data.get("id", "unknown"))
        return QwilrPageResult(
            page_id=data.get("id", ""),
            url=data.get("url", ""),
            share_url=data.get("shareUrl", data.get("url", "")),
            status="published" if request.published else "draft",
        )

    async def update_page(self, page_id: str, **kwargs) -> dict:
        """Update an existing Qwilr page."""
        return await self._request("PUT", f"/pages/{page_id}", json=kwargs)

    async def get_page(self, page_id: str) -> dict:
        """Retrieve a Qwilr page by ID."""
        return await self._request("GET", f"/pages/{page_id}")

    async def delete_page(self, page_id: str) -> None:
        """Delete a Qwilr page."""
        await self._request("DELETE", f"/pages/{page_id}")

    async def list_pages(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """List Qwilr pages."""
        data = await self._request("GET", "/pages", params={"limit": limit, "offset": offset})
        return data if isinstance(data, list) else data.get("pages", data.get("results", []))

    # --- Section/Block Operations ---

    async def create_section(self, page_id: str, block_id: str, quote_sections: list[dict]) -> dict:
        """Insert a saved block (e.g., Quote block) into a page."""
        payload = {
            "blockId": block_id,
            "quoteSections": quote_sections,
        }
        return await self._request("POST", f"/pages/{page_id}/sections", json=payload)

    # --- Template Operations ---

    async def list_templates(self) -> list[dict]:
        """List available Qwilr templates."""
        data = await self._request("GET", "/templates")
        return data if isinstance(data, list) else data.get("templates", data.get("results", []))

    # --- Webhook Operations ---

    async def register_webhook(self, event: str, url: str) -> dict:
        """Register a webhook subscription."""
        return await self._request("POST", "/webhooks", json={"event": event, "url": url})

    async def list_webhooks(self) -> list[dict]:
        """List all webhook subscriptions."""
        data = await self._request("GET", "/webhooks")
        return data if isinstance(data, list) else data.get("webhooks", data.get("results", []))

    async def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook subscription."""
        await self._request("DELETE", f"/webhooks/{webhook_id}")

    # --- Health Check ---

    async def health_check(self) -> bool:
        """Verify API connectivity and authentication."""
        try:
            await self._request("GET", "/pages", params={"limit": 1})
            return True
        except QwilrAPIError:
            return False


class QwilrProposalService:
    """High-level service that orchestrates proposal creation on Qwilr."""

    def __init__(self, client: QwilrClient, config: QwilrConfig):
        self.client = client
        self.config = config

    async def create_proposal_page(
        self,
        page_request: QwilrCreatePageRequest,
        quote_sections: list[dict] | None = None,
        publish: bool = False,
    ) -> QwilrPageResult:
        """Create a complete proposal page with optional quote block.

        1. Creates the page from template with text substitutions
        2. Inserts the interactive Quote block if quote_sections provided
        3. Optionally publishes the page
        """
        # Step 1: Create the base page from template
        result = await self.client.create_page(page_request)
        logger.info("Base page created: %s", result.page_id)

        # Step 2: Insert quote block if we have pricing data and a block ID
        if quote_sections and self.config.quote_block_id:
            try:
                await self.client.create_section(
                    result.page_id,
                    self.config.quote_block_id,
                    quote_sections,
                )
                logger.info("Quote block inserted into page %s", result.page_id)
            except QwilrAPIError as e:
                logger.warning("Failed to insert quote block: %s (page still created)", e)

        # Step 3: Publish if requested
        if publish:
            await self.client.update_page(result.page_id, published=True)
            result.status = "published"
            logger.info("Page %s published", result.page_id)

        return result
