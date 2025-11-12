from datetime import datetime, timezone

from app.models import Attachment, Order


def test_get_order_returns_aggregated_payload(client, db_session):
    order = Order(
        external_id=222222,
        link="https://www.fl.ru/projects/222222/sample.html",
        title="Sample",
        summary="Summary text",
        pub_date=datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc),
        rss_raw={"key": "value"},
        enriched_json={"extra": "info"},
    )
    db_session.add(order)
    db_session.flush()

    attachment = Attachment(
        order_id=order.id,
        filename="doc.pdf",
        stored_path="/tmp/doc.pdf",
        size_bytes=123,
        mime_type="application/pdf",
        original_url="https://www.fl.ru/download/doc.pdf",
        page_url=order.link,
        sha256="hashvalue",
    )
    db_session.add(attachment)
    db_session.commit()

    response = client.get(f"/api/orders/{order.external_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["external_id"] == order.external_id
    assert body["summary"] == "Summary text"
    assert body["rss_raw"]["key"] == "value"
    assert body["enriched"]["extra"] == "info"
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["filename"] == "doc.pdf"


def test_list_orders_filters(client, db_session):
    order1 = Order(
        external_id=300001,
        link="https://www.fl.ru/projects/300001/one.html",
        title="First",
        summary="First summary",
        rss_raw={},
        enriched_json={},
    )
    order2 = Order(
        external_id=300002,
        link="https://www.fl.ru/projects/300002/two.html",
        title="Second",
        summary="Second summary",
        rss_raw={},
        enriched_json={},
    )
    db_session.add_all([order1, order2])
    db_session.flush()

    attachment = Attachment(
        order_id=order1.id,
        filename="file.txt",
        stored_path="/tmp/file.txt",
        size_bytes=10,
    )
    db_session.add(attachment)
    db_session.commit()

    response = client.get("/api/orders", params={"has_attachments": True})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["external_id"] == order1.external_id

    response = client.get("/api/orders", params={"q": "Second"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["external_id"] == order2.external_id
