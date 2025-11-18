from __future__ import annotations

import logging
from typing import Any, Mapping

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class StagehandServiceError(RuntimeError):
    """Raised when Stagehand service returns an error."""


async def parse_site(
    url: str,
    *,
    instruction: str | None = None,
    schema: Mapping[str, Any] | None = None,
    options: Mapping[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    settings = get_settings()
    base_url = settings.stagehand_service_url.rstrip("/")
    payload: dict[str, Any] = {"url": url}
    if instruction:
        payload["instruction"] = instruction
    if schema is not None:
        payload["schema"] = schema
    if options is not None:
        payload["options"] = options

    logger.info("Sending Stagehand extraction request", extra={"url": url})

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{base_url}/stagehand/extract", json=payload)
    except httpx.RequestError as exc:
        logger.exception("Failed to call Stagehand service")
        raise StagehandServiceError(f"Could not reach Stagehand service: {exc}") from exc

    if response.status_code >= 400:
        logger.error(
            "Stagehand service returned error", extra={"status": response.status_code, "body": response.text}
        )
        raise StagehandServiceError(
            f"Stagehand service error {response.status_code}: {response.text}",
        )

    try:
        data = response.json()
    except ValueError as exc:
        logger.exception("Invalid JSON from Stagehand service")
        raise StagehandServiceError("Invalid JSON returned from Stagehand service") from exc

    return data
