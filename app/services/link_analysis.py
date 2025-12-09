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
    if order_id is None and user_uid is None:
        return

    normalized_urls = [normalize_url(url) for url in urls]
    new_urls_set = set(merge_links(normalized_urls))

    session: Session = SessionLocal()
    try:
        existing_order_urls: set[str] = set()
        existing_user_urls: set[str] = set()

        if order_id is not None:
            existing_order_urls = {
                row.url
                for row in session.query(OrderLinkAnalysis)
                .filter_by(order_id=order_id)
                .all()
            }
        if user_uid is not None:
            existing_user_urls = {
                row.url
                for row in session.query(UserLinkAnalysis)
                .filter_by(user_uid=user_uid)
                .all()
            }

        urls_to_add_order = new_urls_set - existing_order_urls if order_id is not None else set()
        urls_to_delete_order = existing_order_urls - new_urls_set if order_id is not None else set()

        urls_to_add_user = new_urls_set - existing_user_urls if user_uid is not None else set()
        urls_to_delete_user = existing_user_urls - new_urls_set if user_uid is not None else set()

        urls_to_analyze = urls_to_add_order | urls_to_add_user
        analysis_by_url: dict[str, dict] = {}
        if urls_to_analyze:
            urls_to_analyze_list = list(urls_to_analyze)
            results = await asyncio.gather(*[_analyze_single(url) for url in urls_to_analyze_list])
            analysis_by_url = {
                url: payload
                for url, payload in zip(urls_to_analyze_list, results)
                if payload is not None
            }

        if order_id is not None and urls_to_delete_order:
            (
                session.query(OrderLinkAnalysis)
                .filter(
                    OrderLinkAnalysis.order_id == order_id,
                    OrderLinkAnalysis.url.in_(urls_to_delete_order),
                )
                .delete(synchronize_session=False)
            )
        if user_uid is not None and urls_to_delete_user:
            (
                session.query(UserLinkAnalysis)
                .filter(
                    UserLinkAnalysis.user_uid == user_uid,
                    UserLinkAnalysis.url.in_(urls_to_delete_user),
                )
                .delete(synchronize_session=False)
            )

        if order_id is not None:
            for url in urls_to_add_order:
                payload = analysis_by_url.get(url)
                if payload is None:
                    continue
                session.add(
                    OrderLinkAnalysis(order_id=order_id, url=url, analysis_json=payload)
                )

        if user_uid is not None:
            for url in urls_to_add_user:
                payload = analysis_by_url.get(url)
                if payload is None:
                    continue
                session.add(
                    UserLinkAnalysis(user_uid=user_uid, url=url, analysis_json=payload)
                )

        session.commit()
    except Exception:
        session.rollback()
        logger.exception(
            "Failed to persist link analysis",
            extra={"order_id": order_id, "user_uid": str(user_uid) if user_uid is not None else None},
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
