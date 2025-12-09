from __future__ import annotations

import logging
import re
from typing import Iterable
from urllib.parse import parse_qs, unquote, urlsplit, urlunsplit

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    return urlunsplit((scheme, netloc, parts.path, parts.query, parts.fragment))


def _unwrap_fl_redirect(url: str) -> str:
    if "fl.ru/away" not in url:
        return url
    try:
        query = parse_qs(urlsplit(url).query)
        href_value = query.get("href", [None])[0]
        if href_value:
            return unquote(href_value)
    except Exception:  # pragma: no cover - defensive fallback
        logger.debug("Failed to unwrap fl redirect", exc_info=True)
    return url


def normalized_link_key(url: str) -> str:
    """Normalization key used for deduplication and analysis."""

    return normalize_url(_unwrap_fl_redirect(url))


def extract_links(text: str | None) -> list[str]:
    if not text:
        return []
    seen: set[str] = set()
    links: list[str] = []
    for match in URL_PATTERN.finditer(text):
        raw = match.group(0).rstrip('.,")\'\u00bb')
        normalized = normalized_link_key(raw)
        if normalized not in seen:
            seen.add(normalized)
            links.append(raw)
    return links


def merge_links(*sources: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for source in sources:
        for item in source:
            if item not in seen:
                seen.add(item)
                result.append(item)
    return result

