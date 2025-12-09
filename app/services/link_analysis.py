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
    if not unique_urls or (order_id is None and user_uid is None):
        return

    session: Session = SessionLocal()
    try:
        current_urls = set(unique_urls)

        existing_order_urls: set[str] = set()
        if order_id is not None:
            existing_order_urls = {
                url
                for (url,) in session.query(OrderLinkAnalysis.url).filter(
                    OrderLinkAnalysis.order_id == order_id
                )
            }

        existing_user_urls: set[str] = set()
        if user_uid is not None:
            existing_user_urls = {
                url
                for (url,) in session.query(UserLinkAnalysis.url).filter(
                    UserLinkAnalysis.user_uid == user_uid
                )
            }

        new_order_urls = current_urls - existing_order_urls if order_id is not None else set()
        urls_to_delete_order = existing_order_urls - current_urls if order_id is not None else set()

        new_user_urls = current_urls - existing_user_urls if user_uid is not None else set()
        urls_to_delete_user = existing_user_urls - current_urls if user_uid is not None else set()

        urls_to_analyze = set()
        urls_to_analyze.update(new_order_urls)
        urls_to_analyze.update(new_user_urls)

        analyzed_urls = list(urls_to_analyze)
        results = await asyncio.gather(*[_analyze_single(url) for url in analyzed_urls])

        if order_id is not None and urls_to_delete_order:
            session.query(OrderLinkAnalysis).filter(
                OrderLinkAnalysis.order_id == order_id,
                OrderLinkAnalysis.url.in_(urls_to_delete_order),
            ).delete(synchronize_session=False)

        if user_uid is not None and urls_to_delete_user:
            session.query(UserLinkAnalysis).filter(
                UserLinkAnalysis.user_uid == user_uid,
                UserLinkAnalysis.url.in_(urls_to_delete_user),
            ).delete(synchronize_session=False)

        for url, payload in zip(analyzed_urls, results):
            if payload is None:
                continue
            if order_id is not None and url in new_order_urls:
                session.add(OrderLinkAnalysis(order_id=order_id, url=url, analysis_json=payload))
            if user_uid is not None and url in new_user_urls:
                session.add(UserLinkAnalysis(user_uid=user_uid, url=url, analysis_json=payload))

        session.commit()
    except Exception:
        session.rollback()
        logger.exception(
            "Failed to persist link analysis",
            extra={"order_id": order_id, "user_uid": str(user_uid) if user_uid else None},
        )
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
