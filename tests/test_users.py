import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.models import UserAttachment, User


def _create_user(client) -> uuid.UUID:
    response = client.post("/api/users", json={"meta": {"source": "test"}})
    assert response.status_code == 200
    data = response.json()
    return uuid.UUID(data["uid"])


def test_create_user_returns_uuid(client):
    response = client.post("/api/users", json={"meta": {"foo": "bar"}})
    assert response.status_code == 200
    data = response.json()
    assert "uid" in data
    uid_value = uuid.UUID(data["uid"])
    assert isinstance(uid_value, uuid.UUID)


def test_patch_user_updates_text_and_categories(client, db_session):
    uid = _create_user(client)

    payload = {
        "competencies_text": "Senior Python Developer",
        "categories": ["Frontend", "Go", "  AI  ", "frontend", ""],
    }

    response = client.patch(f"/api/users/{uid}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["competencies_text"] == "Senior Python Developer"
    assert data["categories"] == ["frontend", "go", "ai"]

    stored_user = db_session.get(User, uid)
    assert stored_user is not None
    assert stored_user.competencies_text == "Senior Python Developer"
    assert stored_user.categories == ["frontend", "go", "ai"]


def test_upload_user_files_and_hash(client, db_session):
    uid = _create_user(client)

    files = [
        ("files", ("portfolio.txt", b"portfolio content", "text/plain")),
        ("files", ("resume.pdf", b"resume pdf", "application/pdf")),
    ]

    response = client.post(f"/api/users/{uid}/files", files=files)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2

    expected = {
        hashlib.sha256(b"portfolio content").hexdigest(): len(b"portfolio content"),
        hashlib.sha256(b"resume pdf").hexdigest(): len(b"resume pdf"),
    }

    for item in body:
        sha = item["sha256"]
        assert sha in expected
        assert item["size"] == expected[sha]
        assert Path(item["stored_path"]).exists()
        if item["content_type"] == "text/plain":
            assert item["filename"].endswith(".txt")
        if item["content_type"] == "application/pdf":
            assert item["filename"].endswith(".pdf")

    attachments = db_session.scalars(select(UserAttachment).where(UserAttachment.user_uid == uid)).all()
    assert len(attachments) == 2


def test_get_user_returns_attachments(client):
    uid = _create_user(client)

    files = [
        ("files", ("portfolio.txt", b"portfolio", "text/plain")),
        ("files", ("cv.doc", b"curriculum", "application/msword")),
    ]
    upload_response = client.post(f"/api/users/{uid}/files", files=files)
    assert upload_response.status_code == 200

    response = client.get(f"/api/users/{uid}")
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == str(uid)
    assert len(data["attachments"]) == 2
    first_attachment = data["attachments"][0]
    second_attachment = data["attachments"][1]
    assert first_attachment["created_at"] <= second_attachment["created_at"]


def test_upload_over_limit_returns_413_and_no_file_on_disk(client):
    settings = get_settings()
    original_limit = settings.max_upload_mb
    settings.max_upload_mb = 1
    try:
        uid = _create_user(client)
        oversized_content = b"x" * (2 * 1024 * 1024)
        files = [("files", ("oversized.bin", oversized_content, "application/octet-stream"))]

        response = client.post(f"/api/users/{uid}/files", files=files)
        assert response.status_code == 413

        user_dir = settings.upload_dir / f"user_{uid}"
        if user_dir.exists():
            has_files = any(path.is_file() for path in user_dir.rglob("*"))
            assert not has_files
    finally:
        settings.max_upload_mb = original_limit
