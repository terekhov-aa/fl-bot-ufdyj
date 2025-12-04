from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

import base64
import mimetypes

from ..config import get_settings
from ..db import SessionLocal
from ..models import Attachment, AttachmentAnalysis
from ..utils.file_types import AttachmentKind, classify_extension, suffix_for_filename

logger = logging.getLogger(__name__)

MAX_TEXT_PREVIEW_CHARS = 40_000


async def analyze_and_update_attachment(session: Session, attachment_id: int) -> None:
    """Определяет тип вложения, анализирует его и сохраняет описание."""

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

    ext = suffix_for_filename(file_path.name)
    kind = classify_extension(ext)

    client = AsyncOpenAI(api_key=settings.llm_api_key)

    description: Optional[str]
    try:
        if kind is AttachmentKind.IMAGE:
            description = await _analyze_image_file(client, settings, file_path)
        elif kind is AttachmentKind.PDF:
            description = await _analyze_pdf_file(client, settings, file_path)
        elif kind in (AttachmentKind.TEXT, AttachmentKind.CODE):
            description = await _analyze_text_like_file(client, settings, file_path, kind)
        elif kind is AttachmentKind.AUDIO:
            description = await _analyze_audio_file(client, settings, file_path)
        elif kind in (
            AttachmentKind.OFFICE_TEXT,
            AttachmentKind.OFFICE_SHEET,
            AttachmentKind.OFFICE_PRESENTATION,
        ):
            description = _fallback_office_description(ext)
        elif kind is AttachmentKind.VIDEO:
            description = _fallback_video_description(ext)
        elif kind in (AttachmentKind.ARCHIVE, AttachmentKind.BINARY):
            description = _fallback_binary_description(ext)
        else:
            description = _fallback_unknown_description(ext)
    except Exception as exc:  # pragma: no cover - анализ не должен ломать загрузку
        logger.error(
            "Unexpected error during attachment analysis",
            exc_info=exc,
            extra={"attachment_id": attachment_id, "kind": kind.value},
        )
        return

    if description:
        attachment.description = description
        analysis = AttachmentAnalysis(attachment_id=attachment_id, description=description)
        session.add(analysis)
        session.commit()
        logger.info(
            "Attachment description updated",
            extra={"attachment_id": attachment_id, "kind": kind.value},
        )


async def analyze_attachment_detached(attachment_id: int) -> None:
    session = SessionLocal()
    try:
        await analyze_and_update_attachment(session, attachment_id)
    finally:
        session.close()


async def _analyze_image_file(client: AsyncOpenAI, settings, file_path: Path) -> Optional[str]:
    """Анализ изображения через Responses API (input_image + data URL)."""
    try:
        # Определяем mime-тип (image/png, image/jpeg и т.п.)
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "image/png"

        # Читаем файл и кодируем в base64 → data URL
        image_bytes = file_path.read_bytes()
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{b64}"
    except Exception as exc:  # pragma: no cover
        logger.error(
            "Failed to prepare image for analysis",
            exc_info=exc,
            extra={"path": str(file_path)},
        )
        return None

    try:
        response = await client.responses.create(
            model=settings.openai_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Ты помощник для сервиса заказов с FL.ru. "
                                "Кратко (1–2 предложения) опиши содержимое изображения "
                                "для карточки вложения. Пиши по-русски."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": data_url,
                            "detail": "low",  # можно убрать, если не нужно
                        },
                    ],
                }
            ],
            max_output_tokens=256,
        )
    except Exception as exc:  # pragma: no cover
        logger.error(
            "OpenAI image analysis failed",
            exc_info=exc,
            extra={"path": str(file_path)},
        )
        return None

    return _extract_response_text(response)


async def _analyze_pdf_file(client: AsyncOpenAI, settings, file_path: Path) -> Optional[str]:
    try:
        with file_path.open("rb") as file_handle:
            uploaded_file = await client.files.create(file=file_handle, purpose="user_data")
    except Exception as exc:  # pragma: no cover
        logger.error(
            "Failed to upload PDF for analysis",
            exc_info=exc,
            extra={"path": str(file_path)},
        )
        return None

    try:
        response = await client.responses.create(
            model=settings.openai_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Ты помощник для сервиса заказов с FL.ru. "
                                "Кратко (1–2 предложения) опиши содержимое PDF-файла "
                                "для карточки вложения. Пиши по-русски."
                            ),
                        },
                        {"type": "input_file", "file_id": uploaded_file.id},
                    ],
                }
            ],
            max_output_tokens=256,
        )
    except Exception as exc:  # pragma: no cover
        logger.error(
            "OpenAI PDF analysis failed",
            exc_info=exc,
            extra={"path": str(file_path)},
        )
        return None

    return _extract_response_text(response)


async def _analyze_text_like_file(
    client: AsyncOpenAI,
    settings,
    file_path: Path,
    kind: AttachmentKind,
) -> Optional[str]:
    try:
        text_content = _read_text_preview(file_path)
    except Exception as exc:  # pragma: no cover
        logger.error(
            "Failed to read text-like file",
            exc_info=exc,
            extra={"path": str(file_path)},
        )
        return None

    if not text_content:
        logger.warning("Empty text content for analysis", extra={"path": str(file_path)})
        return None

    try:
        response = await client.responses.create(
            model=settings.openai_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Ты помощник для сервиса заказов с FL.ru. "
                                "Кратко (1–2 предложения) опиши содержимое файла "
                                "для карточки вложения. Пиши по-русски.\n\n" + text_content
                            ),
                        }
                    ],
                }
            ],
            max_output_tokens=256,
        )
    except Exception as exc:  # pragma: no cover
        logger.error(
            "OpenAI text analysis failed",
            exc_info=exc,
            extra={"path": str(file_path), "kind": kind.value},
        )
        return None

    return _extract_response_text(response)


async def _analyze_audio_file(client: AsyncOpenAI, settings, file_path: Path) -> Optional[str]:
    try:
        with file_path.open("rb") as file_handle:
            transcription = await client.audio.transcriptions.create(
                model=settings.speech_model,
                file=file_handle,
            )
    except Exception as exc:  # pragma: no cover
        logger.error(
            "Audio transcription failed",
            exc_info=exc,
            extra={"path": str(file_path)},
        )
        return None

    transcript_text = getattr(transcription, "text", "") or ""
    transcript_text = transcript_text.strip()
    if not transcript_text:
        logger.warning("Empty transcription result", extra={"path": str(file_path)})
        return None

    try:
        response = await client.responses.create(
            model=settings.openai_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "У тебя есть транскрипт аудио из заказа FL.ru. "
                                "Кратко (1–2 предложения) опиши, о чём аудио, по-русски.\n\n"
                                + transcript_text
                            ),
                        }
                    ],
                }
            ],
            max_output_tokens=256,
        )
    except Exception as exc:  # pragma: no cover
        logger.error(
            "OpenAI audio summary failed",
            exc_info=exc,
            extra={"path": str(file_path)},
        )
        return None

    return _extract_response_text(response)


def _read_text_preview(file_path: Path, max_chars: int = MAX_TEXT_PREVIEW_CHARS) -> str:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    if len(text) > max_chars:
        return text[:max_chars]
    return text


def _extract_response_text(response) -> Optional[str]:
    try:
        output_text = getattr(response, "output_text", None)
        if output_text:
            text_value = output_text.strip()
            if text_value:
                return text_value
    except Exception:
        pass

    try:
        if response.output and response.output[0].content:
            first_part = response.output[0].content[0]
            text_obj = getattr(first_part, "text", None)
            if text_obj is not None:
                text_value = (getattr(text_obj, "value", None) or "").strip()
                if text_value:
                    return text_value
    except Exception:
        return None
    return None


def _fallback_office_description(ext: str) -> str:
    return f"Файл формата {ext}. Автоматический анализ офисных документов пока не поддерживается."


def _fallback_video_description(ext: str) -> str:
    return f"Видео-файл формата {ext}. Автоматический анализ видео пока не поддерживается."


def _fallback_binary_description(ext: str) -> str:
    return f"Файл формата {ext}. Автоматический анализ содержимого пока не поддерживается."


def _fallback_unknown_description(ext: str) -> str:
    return f"Файл неизвестного типа ({ext}). Автоматический анализ пока не настроен."
