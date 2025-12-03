from __future__ import annotations

import asyncio
import logging
from typing import Iterable

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal
from ..models import OrderLinkAnalysis, UserLinkAnalysis
from ..utils.links import extract_links, merge_links, normalize_url

logger = logging.getLogger(__name__)


async def _analyze_single(url: str) -> dict | None:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(settings.link_analyzer_url, json={"url": url})
    except httpx.RequestError as exc:  # pragma: no cover - network errors
        logger.error("Link analyzer request failed", exc_info=exc, extra={"url": url})
        return None
    if response.status_code >= 400:
        logger.warning(
            "Link analyzer returned error", extra={"url": url, "status": response.status_code}
        )
        return None
    try:
        return response.json()
    except Exception:
        logger.error("Invalid JSON from link analyzer", extra={"url": url})
        return None


async def analyze_links_and_store(
    urls: Iterable[str], *, order_id: int | None = None, user_uid=None
) -> None:
    unique_urls = merge_links([normalize_url(url) for url in urls])
    if not unique_urls:
        return

    results = await asyncio.gather(*[_analyze_single(url) for url in unique_urls])
    session: Session = SessionLocal()
    try:
        for url, payload in zip(unique_urls, results):
            if payload is None:
                continue
            if order_id is not None:
                session.add(OrderLinkAnalysis(order_id=order_id, url=url, analysis_json=payload))
            if user_uid is not None:
                session.add(UserLinkAnalysis(user_uid=user_uid, url=url, analysis_json=payload))
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to persist link analysis", extra={"order_id": order_id, "user_uid": str(user_uid) if user_uid else None})
    finally:
        session.close()


def schedule_link_analysis(urls: Iterable[str], *, order_id: int | None = None, user_uid=None) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # pragma: no cover - sync context
        return
    loop.create_task(analyze_links_and_store(urls, order_id=order_id, user_uid=user_uid))


__all__ = [
    "analyze_links_and_store",
    "schedule_link_analysis",
    "extract_links",
]
