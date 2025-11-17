from __future__ import annotations
from __future__ import annotations

import os

if os.getenv("PYCHARM_DEBUG") == "1":
    import pydevd_pycharm
    # чтобы не подключаться дважды под --reload:
    if not getattr(pydevd_pycharm, "get_global_debugger", lambda: None)():
        pydevd_pycharm.settrace(
            'host.docker.internal',
            port=5678,
            stdout_to_server=True,   # <-- было stdoutToServer
            stderr_to_server=True,   # <-- было stderrToServer
            suspend=False
        )

import asyncio
import hashlib
import logging
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from logging.config import dictConfig
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import feedparser
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes import debug_browserbase, ingest, orders, upload, feedbacks
from .routers import users
from .utils.parsing import extract_external_id


def configure_logging() -> None:
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            }
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            }
        },
        "root": {
            "handlers": ["default"],
            "level": "INFO",
        },
    }
    dictConfig(logging_config)


configure_logging()

app = FastAPI(title="FL.ru Order Aggregator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(upload.router)
app.include_router(orders.router)
app.include_router(users.router)
app.include_router(feedbacks.router)
app.include_router(debug_browserbase.router)


@app.on_event("startup")
def on_startup() -> None:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
    try:
        settings.upload_dir.chmod(0o755)
    except PermissionError:
        pass


URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)

pool: Any | None = None


def _clean_summary(summary: str | None) -> str:
    if summary is None:
        return ""
    return summary.replace("\r", "").strip()


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    return urlunsplit((scheme, netloc, parts.path, parts.query, parts.fragment))


def _extract_links(summary: str) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for match in URL_PATTERN.finditer(summary):
        raw = match.group(0).rstrip('.,")\'\u00bb')
        normalized = _normalize_url(raw)
        if normalized not in seen:
            seen.add(normalized)
            links.append(normalized)
    return links


def _parse_pub_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        else:
            dt = dt.astimezone(UTC)
        return dt
    except (TypeError, ValueError):
        return None


def parse_and_normalize_fl_feed(rss_bytes: bytes) -> list[dict[str, Any]]:
    parsed = feedparser.parse(rss_bytes)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        summary_raw = entry.get("summary") or entry.get("description") or ""
        summary = _clean_summary(summary_raw)
        links = _extract_links(summary)
        pub_date = _parse_pub_date(entry.get("published") or entry.get("pubDate"))
        external_id = extract_external_id(entry.get("link"))
        items.append(
            {
                "external_id": external_id,
                "link": entry.get("link", ""),
                "title": entry.get("title", ""),
                "summary": summary,
                "published": pub_date,
                "links": links,
            }
        )
    return items


async def upsert_fl_orders(items: Iterable[dict[str, Any]]) -> dict[str, int]:
    if pool is None:
        raise RuntimeError("Database pool is not configured")
    stats = {"seen": 0, "inserted": 0, "skipped": 0}
    async with pool.connection() as connection:
        async with connection.cursor() as cursor:
            for item in items:
                stats["seen"] += 1
                params = (
                    item.get("external_id"),
                    item.get("link"),
                    item.get("title"),
                    item.get("summary"),
                    item.get("published"),
                )
                await cursor.execute(
                    "INSERT INTO app.fl_orders (external_id, link, title, summary, published) "
                    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id, inserted",
                    params,
                )
                row = await cursor.fetchone()
                inserted = False
                order_id = item.get("external_id")
                if row:
                    order_id = row[0]
                    inserted = bool(row[1]) if len(row) > 1 else True
                if inserted:
                    stats["inserted"] += 1
                else:
                    stats["skipped"] += 1
                for link in item.get("links", []):
                    await cursor.execute(
                        "INSERT INTO app.fl_order_links (order_id, link, url_hash) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                        (
                            order_id,
                            link,
                            hashlib.sha256(link.encode("utf-8")).hexdigest(),
                        ),
                    )
    return stats


async def list_fl_messages(*, limit: int = 20) -> list[dict[str, Any]]:
    if pool is None:
        raise RuntimeError("Database pool is not configured")
    async with pool.connection() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "SELECT id, title, link, published, summary FROM app.fl_orders ORDER BY published DESC LIMIT %s",
                (limit,),
            )
            rows = await cursor.fetchall()

    messages: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            data = row
        else:
            order_id, title, link, published, summary = row
            data = {
                "id": order_id,
                "title": title,
                "link": link,
                "published": published,
                "summary": summary,
            }
        published = data.get("published")
        published_iso = published.isoformat() if isinstance(published, datetime) else published
        messages.append(
            {
                "id": data.get("id"),
                "title": data.get("title"),
                "link": data.get("link"),
                "summary": data.get("summary"),
                "published": published_iso,
            }
        )
    return messages
