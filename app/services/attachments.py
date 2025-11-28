from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Attachment

logger = logging.getLogger(__name__)


async def analyze_and_update_attachment(session: Session, attachment_id: int) -> None:
    """Отправляет вложение в внешний анализатор и сохраняет его описание в БД."""

    attachment: Optional[Attachment] = session.get(Attachment, attachment_id)
    if attachment is None:
        logger.warning("Attachment not found for analysis", extra={"attachment_id": attachment_id})
        return

    settings = get_settings()
    analyzer_url = settings.file_analyzer_url
    if not analyzer_url:
        logger.info("File analyzer URL is not configured; skipping analysis", extra={"attachment_id": attachment_id})
        return

    file_path = Path(attachment.stored_path)
    if not file_path.exists():
        logger.error("Stored attachment path does not exist", extra={"attachment_id": attachment_id, "path": attachment.stored_path})
        return

    try:
        with file_path.open("rb") as file_handle:
            files = {
                "file": (attachment.filename, file_handle, attachment.mime_type or "application/octet-stream"),
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(analyzer_url, files=files)
    except httpx.RequestError as exc:  # pragma: no cover - network errors
        logger.error("File analyzer request failed", exc_info=exc, extra={"attachment_id": attachment_id})
        return
    except Exception as exc:  # pragma: no cover - unexpected file IO errors
        logger.error("Failed to read attachment for analysis", exc_info=exc, extra={"attachment_id": attachment_id})
        return

    if response.status_code >= 500:
        logger.error("File analyzer returned server error", extra={"status_code": response.status_code, "attachment_id": attachment_id})
        return

    if response.status_code >= 400:
        logger.warning(
            "File analyzer returned client error",
            extra={"status_code": response.status_code, "attachment_id": attachment_id, "response": response.text},
        )
        return

    try:
        payload = response.json()
    except ValueError:
        logger.error("File analyzer returned invalid JSON", extra={"attachment_id": attachment_id, "response": response.text})
        return

    description = payload.get("description") if isinstance(payload, dict) else None
    if not isinstance(description, str):
        logger.warning(
            "File analyzer response does not contain description",
            extra={"attachment_id": attachment_id, "payload": payload},
        )
        return

    attachment.description = description
    session.commit()
    logger.info("Attachment description updated from analyzer", extra={"attachment_id": attachment_id})
