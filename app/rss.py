from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import RSSIngestOptions, get_settings
from .services.orders import upsert_order_from_rss
from .utils.parsing import extract_external_id
from .utils.time import parse_rss_date

logger = logging.getLogger(__name__)


def build_feed_url(options: RSSIngestOptions) -> str:
    settings = get_settings()
    base_url = options.feed_url or settings.rss_feed_url
    query_params = {}
    category = options.category if options.category is not None else settings.rss_category
    subcategory = options.subcategory if options.subcategory is not None else settings.rss_subcategory
    if category is not None:
        query_params["category"] = category
    if subcategory is not None:
        query_params["subcategory"] = subcategory
    parsed = urlparse(base_url)
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))
    existing.update({k: str(v) for k, v in query_params.items()})
    query = urlencode(existing, doseq=True)
    parsed = parsed._replace(query=query)
    final_url = urlunparse(parsed)
    return final_url


def ingest_rss(session: Session, options: RSSIngestOptions) -> tuple[int, int]:
    feed_url = build_feed_url(options)
    logger.info("Fetching RSS feed", extra={"feed_url": feed_url})
    try:
        parsed_feed = feedparser.parse('https://www.fl.ru/rss/all.xml')
    except Exception as exc:  # pragma: no cover - defensive network handling
        logger.exception("Failed to fetch RSS feed", extra={"feed_url": feed_url})
        raise HTTPException(status_code=502, detail="Failed to fetch RSS feed") from exc
    if getattr(parsed_feed, "bozo", False):
        logger.error(
            "Failed to parse RSS feed",
            extra={"feed_url": feed_url},
            exc_info=getattr(parsed_feed, "bozo_exception", None),
        )
        raise HTTPException(status_code=502, detail="Failed to parse RSS feed")
    status = getattr(parsed_feed, "status", 200)
    if isinstance(status, int) and status >= 400:
        logger.error("RSS feed responded with error", extra={"feed_url": feed_url, "status": status})
        raise HTTPException(status_code=502, detail="Failed to fetch RSS feed")
    entries = parsed_feed.entries
    logger.info("RSS feed parsed", extra={"feed_url": feed_url, "entries": len(entries)})
    limit = options.limit
    if limit is not None:
        entries = entries[:limit]
    inserted = 0
    updated = 0
    for entry in entries:
        link = entry.get("link")
        title = entry.get("title", "")
        if not link or not title:
            logger.warning("Skipping entry without link/title", extra={"entry": entry})
            continue
        summary = entry.get("summary") or entry.get("description")
        pub_date = parse_rss_date(entry.get("published") or entry.get("pubDate"))
        external_id = extract_external_id(link)
        rss_raw = {key: value for key, value in entry.items()}
        order, created = upsert_order_from_rss(
            session,
            external_id=external_id,
            link=link,
            title=title,
            summary=summary,
            pub_date=pub_date,
            rss_raw=rss_raw,
        )
        if created:
            inserted += 1
        else:
            updated += 1
    logger.info("RSS ingest complete", extra={"inserted": inserted, "updated": updated})
    return inserted, updated
