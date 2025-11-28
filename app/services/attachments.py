from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from openai import AsyncOpenAI

from ..config import Settings, get_settings
from ..models import Attachment
from ..utils.file_types import AttachmentKind, classify_extension

logger = logging.getLogger(__name__)

AUDIO_MODEL = "gpt-4o-mini-transcribe"
MAX_TEXT_CHARS = 20_000
MAX_OUTPUT_TOKENS = 256


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

    ext = file_path.suffix.lower()
    kind = classify_extension(ext)

    client = AsyncOpenAI(api_key=settings.llm_api_key)

    try:
        if kind is AttachmentKind.IMAGE:
            description = await _analyze_image_file(client, settings, file_path, attachment)
        elif kind is AttachmentKind.PDF:
            description = await _analyze_pdf_file(client, settings, file_path, attachment)
        elif kind in (AttachmentKind.TEXT, AttachmentKind.CODE):
            description = await _analyze_text_like_file(client, settings, file_path, attachment, kind)
        elif kind is AttachmentKind.AUDIO:
            description = await _analyze_audio_file(client, settings, file_path, attachment)
        elif kind in (AttachmentKind.OFFICE_TEXT, AttachmentKind.OFFICE_SHEET, AttachmentKind.OFFICE_PRESENTATION):
            description = _fallback_office_description(ext)
        elif kind is AttachmentKind.VIDEO:
            description = _fallback_video_description(ext)
        elif kind in (AttachmentKind.ARCHIVE, AttachmentKind.BINARY):
            description = _fallback_binary_description(ext)
        else:
            description = _fallback_unknown_description(ext)
    except Exception as exc:  # pragma: no cover
        logger.error(
            "Attachment analysis failed",
            exc_info=exc,
            extra={"attachment_id": attachment_id, "kind": kind.value, "ext": ext},
        )
        return

    if description:
        attachment.description = description
        session.commit()
        logger.info(
            "Attachment description updated",
            extra={"attachment_id": attachment_id, "kind": kind.value},
        )


async def _analyze_image_file(
    client: AsyncOpenAI, settings: Settings, file_path: Path, attachment: Attachment
) -> Optional[str]:
    try:
        with file_path.open("rb") as file_handle:
            uploaded_file = await client.files.create(file=file_handle, purpose="vision")
    except Exception as exc:  # pragma: no cover
        logger.error(
            "Failed to upload image for analysis",
            exc_info=exc,
            extra={"attachment_id": attachment.id, "path": str(file_path)},
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
                                "Кратко (1–2 предложения) опиши содержимое прикреплённого изображения "
                                "для карточки вложения. Пиши по-русски."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": {"file_id": uploaded_file.id},
                        },
                    ],
                }
            ],
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    except Exception as exc:  # pragma: no cover
        logger.error(
            "OpenAI vision analysis failed",
            exc_info=exc,
            extra={"attachment_id": attachment.id},
        )
        return None

    return _extract_output_text(response)


async def _analyze_pdf_file(
    client: AsyncOpenAI, settings: Settings, file_path: Path, attachment: Attachment
) -> Optional[str]:
    try:
        with file_path.open("rb") as file_handle:
            uploaded_file = await client.files.create(file=file_handle, purpose="user_data")
    except Exception as exc:  # pragma: no cover
        logger.error(
            "Failed to upload PDF for analysis",
            exc_info=exc,
            extra={"attachment_id": attachment.id, "path": str(file_path)},
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
                                "Кратко (1–2 предложения) опиши содержимое прикреплённого PDF-файла "
                                "для карточки вложения. Пиши по-русски."
                            ),
                        },
                        {"type": "input_file", "file_id": uploaded_file.id},
                    ],
                }
            ],
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    except Exception as exc:  # pragma: no cover
        logger.error(
            "OpenAI PDF analysis failed",
            exc_info=exc,
            extra={"attachment_id": attachment.id},
        )
        return None

    return _extract_output_text(response)


async def _analyze_text_like_file(
    client: AsyncOpenAI,
    settings: Settings,
    file_path: Path,
    attachment: Attachment,
    kind: AttachmentKind,
) -> Optional[str]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:  # pragma: no cover
        logger.error(
            "Failed to read text-like file",
            exc_info=exc,
            extra={"attachment_id": attachment.id, "path": str(file_path)},
        )
        return None

    truncated = content[:MAX_TEXT_CHARS]
    instruction = (
        "Посмотри на этот текст, кратко опиши, что это за файл и что в нём содержится, 1–2 предложения, по-русски."
        if kind is AttachmentKind.TEXT
        else "Посмотри на этот код, кратко опиши, что это за файл и что в нём содержится, 1–2 предложения, по-русски."
    )

    try:
        response = await client.responses.create(
            model=settings.openai_model,
            input=[{"role": "user", "content": [{"type": "input_text", "text": f"{instruction}\n\n{truncated}"}]}],
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    except Exception as exc:  # pragma: no cover
        logger.error(
            "OpenAI text-like analysis failed",
            exc_info=exc,
            extra={"attachment_id": attachment.id},
        )
        return None

    return _extract_output_text(response)


async def _analyze_audio_file(
    client: AsyncOpenAI, settings: Settings, file_path: Path, attachment: Attachment
) -> Optional[str]:
    try:
        with file_path.open("rb") as audio_file:
            transcription = await client.audio.transcriptions.create(model=AUDIO_MODEL, file=audio_file)
    except Exception as exc:  # pragma: no cover
        logger.error(
            "Audio transcription failed",
            exc_info=exc,
            extra={"attachment_id": attachment.id, "path": str(file_path)},
        )
        return None

    transcript_text = getattr(transcription, "text", "") or ""
    transcript_text = transcript_text[:MAX_TEXT_CHARS]

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
                                "Есть транскрипция аудио. Кратко опиши, о чём это аудио, 1–2 предложения, по-русски.\n\n"
                                f"{transcript_text}"
                            ),
                        }
                    ],
                }
            ],
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    except Exception as exc:  # pragma: no cover
        logger.error(
            "OpenAI audio description failed",
            exc_info=exc,
            extra={"attachment_id": attachment.id},
        )
        return None

    return _extract_output_text(response)


def _extract_output_text(response: object) -> Optional[str]:
    """Extracts text from OpenAI Responses API reply."""

    try:
        text = (getattr(response, "output_text", "") or "").strip()
        if text:
            return text
    except Exception:
        pass

    try:
        output = getattr(response, "output", None)
        if output and output[0].content:
            first_part = output[0].content[0]
            text_obj = getattr(first_part, "text", None)
            if text_obj is not None:
                value = getattr(text_obj, "value", None)
                if value:
                    return str(value).strip()
    except Exception:
        return None
    return None


def _fallback_office_description(ext: str) -> str:
    return (
        f"Файл офисного формата ({ext}). Автоматический анализ содержимого пока не настроен — откройте файл вручную."
    )


def _fallback_video_description(ext: str) -> str:
    return f"Видео-файл формата {ext}. Автоматический анализ видео пока не поддерживается."


def _fallback_binary_description(ext: str) -> str:
    return f"Бинарный файл формата {ext}. Автоматический анализ содержимого пока не поддерживается."


def _fallback_unknown_description(ext: str) -> str:
    return f"Файл неизвестного типа ({ext}). Автоматический анализ пока не настроен."
