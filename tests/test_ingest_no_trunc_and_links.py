from __future__ import annotations

import asyncio
import hashlib
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


def test_parse_and_upsert_preserves_summary_and_links():
    long_tail = "Z" * 2600
    description = (
        "Visit https://Example.com/path?a=1). "
        "Another link http://second.example.com/track,\" "
        "Duplicate: https://example.com/path?a=1 "
        "Trailing char https://third.example.com/doc» "
        + " "
        + long_tail
    )
    rss_bytes = _build_rss(description)

    items = main.parse_and_normalize_fl_feed(rss_bytes)

    assert len(items) == 1
    payload = items[0]
    summary = payload["summary"]
    assert summary is not None
    assert summary.endswith(long_tail)
    assert len(summary) == len(main._clean_summary(description))

    expected_links = [
        "https://example.com/path?a=1",
        "http://second.example.com/track",
        "https://third.example.com/doc",
    ]
    assert main._extract_links(summary) == expected_links

    class RecordingCursor:
        def __init__(self):
            self.link_inserts: list[tuple[int, str, str]] = []
            self.order_params = []
            self._last_row: tuple[int, bool] | None = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - nothing to cleanup
            return False

        async def execute(self, query, params=None):
            if "INSERT INTO app.fl_orders" in query:
                self.order_params.append(params)
                self._last_row = (1, True)
            elif "INSERT INTO app.fl_order_links" in query:
                self.link_inserts.append(params)
                self._last_row = None
            else:  # pragma: no cover - not expected in this test
                self._last_row = None

        async def fetchone(self):
            row = self._last_row
            self._last_row = None
            return row

    class RecordingConnection:
        def __init__(self, cursor):
            self._cursor = cursor

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - nothing to cleanup
            return False

        def cursor(self, **_kwargs):
            return self._cursor

    class RecordingPool:
        def __init__(self, cursor):
            self._cursor = cursor

        def connection(self):
            return RecordingConnection(self._cursor)

    cursor = RecordingCursor()
    original_pool = main.pool
    main.pool = RecordingPool(cursor)
    try:
        stats = asyncio.run(main.upsert_fl_orders(items))
    finally:
        main.pool = original_pool

    assert stats == {"seen": 1, "inserted": 1, "skipped": 0}
    assert [params[1] for params in cursor.link_inserts] == expected_links
    expected_hashes = [hashlib.sha256(url.encode("utf-8")).hexdigest() for url in expected_links]
    assert [params[2] for params in cursor.link_inserts] == expected_hashes

    class ListCursor:
        def __init__(self, rows):
            self._rows = rows

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - nothing to cleanup
            return False

        async def execute(self, *_args, **_kwargs):
            return None

        async def fetchall(self):
            return self._rows

    class ListConnection:
        def __init__(self, rows):
            self._rows = rows

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - nothing to cleanup
            return False

        def cursor(self, **_kwargs):
            return ListCursor(self._rows)

    class ListPool:
        def __init__(self, rows):
            self._rows = rows

        def connection(self):
            return ListConnection(self._rows)

    published = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
    rows = [
        {
            "id": 42,
            "title": payload["title"],
            "link": payload["link"],
            "published": published,
            "summary": summary,
        }
    ]

    original_pool_for_list = main.pool
    main.pool = ListPool(rows)
    try:
        messages = asyncio.run(main.list_fl_messages(limit=1))
    finally:
        main.pool = original_pool_for_list

    assert len(messages) == 1
    message = messages[0]
    assert "preview" not in message
    assert message["summary"] == summary
    assert message["published"] == published.isoformat()
