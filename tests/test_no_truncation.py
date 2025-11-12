from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:  # pragma: no branch - deterministic insertion
    sys.path.insert(0, str(PROJECT_ROOT))

from app import main


def _build_rss(description: str) -> bytes:
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rss version=\"2.0\">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>Example feed</description>
    <item>
      <title>Long summary item</title>
      <link>https://example.com/item</link>
      <guid>1</guid>
      <description><![CDATA[{description}]]></description>
      <pubDate>Mon, 01 Jan 2024 12:00:00 +0300</pubDate>
    </item>
  </channel>
</rss>
""".encode("utf-8")


def test_parse_and_normalize_preserves_full_summary():
    long_text = "A" * 2600
    rss_bytes = _build_rss(long_text)

    items = main.parse_and_normalize_fl_feed(rss_bytes)

    assert len(items) == 1
    summary = items[0]["summary"]
    assert summary is not None
    assert summary == long_text
    assert len(summary) == len(long_text)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - no cleanup
        return False

    async def execute(self, *_args, **_kwargs):
        return None

    async def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - no cleanup
        return False

    def cursor(self, **_kwargs):
        return _FakeCursor(self._rows)


class _FakePool:
    def __init__(self, rows):
        self._rows = rows

    def connection(self):
        return _FakeConnection(self._rows)


def test_list_fl_messages_exposes_full_summary():
    long_text = "B" * 2800
    rows = [
        {
            "id": 1,
            "title": "Long summary item",
            "link": "https://example.com/item",
            "published": datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
            "summary": long_text,
        }
    ]

    original_pool = main.pool
    main.pool = _FakePool(rows)
    try:
        messages = asyncio.run(main.list_fl_messages(limit=1))
    finally:
        main.pool = original_pool

    assert len(messages) == 1
    message = messages[0]
    assert "preview" not in message
    assert message["summary"] == long_text
    assert message["published"] == rows[0]["published"].isoformat()
