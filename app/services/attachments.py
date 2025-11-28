from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy.orm import Session
from openai import AsyncOpenAI

from ..config import get_settings
from ..models import Attachment

logger = logging.getLogger(__name__)


async def analyze_and_update_attachment(session: Session, attachment_id: int) -> None:
    """Отправляет вложение напрямую в OpenAI API и сохраняет текстовое описание."""

    attachment: Optional[Attachment] = session.get(Attachment, attachment_id)
    if attachment is None:
        logger.warning("Attachment not found for analysis", extra={"attachment_id": attachment_id})
        return

    settings = get_settings()

    if not settings.llm_api_key:
        logger.info(
            "OpenAI API key is not configured; skipping analysis",
            extra={"attachment_id": attachment_id},
        )
        return

    file_path = Path(attachment.stored_path)
    if not file_path.exists():
        logger.error(
            "Stored attachment path does not exist",
            extra={"attachment_id": attachment_id, "path": attachment.stored_path},
        )
        return
    logger.error(
        "llm_api_key",
        extra={"llm_api_key": settings.llm_api_key},
    )
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        # base_url можно не трогать — по умолчанию https://api.openai.com/v1
    )

    # 1) Загружаем файл в Files API
    try:
        with file_path.open("rb") as file_handle:
            uploaded_file = await client.files.create(
                file=file_handle,
                purpose="user_data",  # или "assistants", обе опции поддерживаются для файлов :contentReference[oaicite:1]{index=1}
            )
    except Exception as exc:  # pragma: no cover - сетевые/IO-ошибки не должны ломать загрузку
        logger.error(
            "Failed to upload attachment to OpenAI",
            exc_info=exc,
            extra={"attachment_id": attachment_id},
        )
        return

    # 2) Просим модель кратко описать файл через Responses API
    try:
        response = await client.responses.create(
            model=settings.openai_model,  # например, gpt-4.1-mini :contentReference[oaicite:2]{index=2}
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Ты помощник для сервиса заказов с FL.ru. "
                                "Кратко (1–2 предложения) опиши содержимое прикреплённого файла "
                                "для карточки вложения. Пиши по-русски."
                            ),
                        },
                        {
                            "type": "input_file",
                            "file_id": uploaded_file.id,
                        },
                    ],
                }
            ],
            max_output_tokens=256,
        )
    except Exception as exc:  # pragma: no cover
        logger.error(
            "OpenAI file analysis request failed",
            exc_info=exc,
            extra={"attachment_id": attachment_id},
        )
        return

    # В свежих версиях SDK есть удобное поле output_text, собирающее текст из ответа :contentReference[oaicite:3]{index=3}
    description: Optional[str] = None
    try:
        description = (response.output_text or "").strip()  # type: ignore[attr-defined]
    except AttributeError:
        # fallback на явный разбор структуры, если output_text вдруг отсутствует
        try:
            if response.output and response.output[0].content:
                first_part = response.output[0].content[0]
                # в типах Responses API текст лежит внутри output_text.text.value :contentReference[oaicite:4]{index=4}
                text_obj = getattr(first_part, "text", None)
                if text_obj is not None:
                    description = (getattr(text_obj, "value", None) or "").strip()
        except Exception:
            description = None

    if not description:
        logger.warning(
            "OpenAI file analysis did not return description",
            extra={"attachment_id": attachment_id},
        )
        return

    attachment.description = description
    session.commit()
    logger.info(
        "Attachment description updated from OpenAI",
        extra={"attachment_id": attachment_id},
    )
