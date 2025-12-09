from __future__ import annotations

import logging
from typing import Iterable

from ..utils.links import extract_links

logger = logging.getLogger(__name__)


async def _analyze_single(url: str) -> dict | None:
    # Link analyzer service disabled; keeping stub for backwards compatibility.
    logger.info("Link analysis disabled, skipping external call", extra={"url": url})
    return None

    # Previous implementation (disabled):
    # settings = get_settings()
    # try:
    #     async with httpx.AsyncClient(timeout=15.0) as client:
    #         response = await client.post(settings.link_analyzer_url, json={"url": url})
    # except httpx.RequestError as exc:  # pragma: no cover - network errors
    #     logger.error("Link analyzer request failed", exc_info=exc, extra={"url": url})
    #     return None
    # if response.status_code >= 400:
    #     logger.warning(
    #         "Link analyzer returned error",
    #         extra={"url": url, "status": response.status_code},
    #     )
    #     return None
    # try:
    #     return response.json()
    # except Exception:
    #     logger.error("Invalid JSON from link analyzer", extra={"url": url})
    #     return None


async def analyze_links_and_store(
    urls: Iterable[str], *, order_id: int | None = None, user_uid=None
) -> None:
    # Link analyzer service disabled; nothing will be stored.
    logger.info(
        "Link analysis disabled, nothing to store",
        extra={
            "order_id": order_id,
            "user_uid": str(user_uid) if user_uid is not None else None,
        },
    )
    return None

    # Previous implementation (disabled):
    # unique_urls = merge_links([normalize_url(url) for url in urls])
    # if not unique_urls:
    #     return
    #
    # results = await asyncio.gather(*[_analyze_single(url) for url in unique_urls])
    # session: Session = SessionLocal()
    # try:
    #     for url, payload in zip(unique_urls, results):
    #         if payload is None:
    #             continue
    #         if order_id is not None:
    #             session.add(
    #                 OrderLinkAnalysis(order_id=order_id, url=url, analysis_json=payload)
    #             )
    #         if user_uid is not None:
    #             session.add(
    #                 UserLinkAnalysis(user_uid=user_uid, url=url, analysis_json=payload)
    #             )
    #     session.commit()
    # except Exception:
    #     session.rollback()
    #     logger.exception(
    #         "Failed to persist link analysis",
    #         extra={"order_id": order_id, "user_uid": str(user_uid) if user_uid else None},
    #     )
    # finally:
    #     session.close()


def schedule_link_analysis(urls: Iterable[str], *, order_id: int | None = None, user_uid=None) -> None:
    """Disabled: link analyzer service is turned off. Kept for API compatibility."""
    return None


__all__ = [
    "analyze_links_and_store",
    "schedule_link_analysis",
    "extract_links",
]
