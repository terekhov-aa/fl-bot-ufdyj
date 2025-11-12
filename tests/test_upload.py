import json

from sqlalchemy import select

from app.models import Attachment, Order


def test_upload_metadata_enriches_order(client, db_session):
    payload = {
        "id": "987654",
        "url": "https://www.fl.ru/projects/987654/sample.html",
        "title": "Проект",
        "description": "Подробное описание",
        "nested": {"field": "value"},
    }

    response = client.post("/api/upload", data={"projectData": json.dumps(payload, ensure_ascii=False)})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["mode"] == "metadata"

    order = db_session.scalars(select(Order).where(Order.external_id == 987654)).one()
    assert order.enriched_json["title"] == "Проект"
    assert order.enriched_json["nested"]["field"] == "value"


def test_upload_attachment_creates_record(client, db_session):
    order = Order(
        external_id=555555,
        link="https://www.fl.ru/projects/555555/sample.html",
        title="Attachment Test",
        summary=None,
        rss_raw={},
        enriched_json={},
    )
    db_session.add(order)
    db_session.commit()

    file_content = b"hello world"
    files = {"file": ("test.txt", file_content, "text/plain")}
    data = {
        "type": "attachment",
        "project_id": str(order.external_id),
        "filename": "test.txt",
        "page_url": order.link,
    }

    response = client.post("/api/upload", data=data, files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "attachment"
    assert body["file"]["filename"].startswith("test")

    attachment = db_session.scalars(select(Attachment).where(Attachment.order_id == order.id)).one()
    assert attachment.size_bytes == len(file_content)
    assert attachment.sha256 is not None
