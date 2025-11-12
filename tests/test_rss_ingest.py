from types import SimpleNamespace

import feedparser
from sqlalchemy import select

from app.config import RSSIngestOptions
from app.models import Order
from app.rss import ingest_rss


def test_rss_ingest_upsert(db_session, monkeypatch):
    entries = [
        {
            "title": "Test Project",
            "link": "https://www.fl.ru/projects/123456/test.html",
            "summary": "Описание проекта",
            "published": "Wed, 01 May 2024 10:00:00 GMT",
            "extra": "value",
        }
    ]
    fake_feed = SimpleNamespace(entries=entries, bozo=False)

    monkeypatch.setattr(feedparser, "parse", lambda url: fake_feed)

    inserted, updated = ingest_rss(db_session, RSSIngestOptions(limit=10))
    assert inserted == 1
    assert updated == 0

    order = db_session.scalars(select(Order).where(Order.external_id == 123456)).one()
    assert order.summary == "Описание проекта"
    assert order.rss_raw["extra"] == "value"

    entries[0]["title"] = "Updated title"
    inserted2, updated2 = ingest_rss(db_session, RSSIngestOptions(limit=10))
    assert inserted2 == 0
    assert updated2 == 1

    db_session.refresh(order)
    assert order.title == "Updated title"
