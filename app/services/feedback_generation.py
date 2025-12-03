from __future__ import annotations

import json
import logging
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (
    Attachment,
    Order,
    OrderFeedback,
    OrderLinkAnalysis,
    User,
    UserAttachment,
    UserLinkAnalysis,
)
from .attachments import _extract_response_text

logger = logging.getLogger(__name__)

MAX_SECTION_LENGTH = 1200
MAX_JSON_SECTION_LENGTH = 1500
MAX_ITEM_COUNT = 10


def _truncate_text(value: str | None, max_length: int = MAX_SECTION_LENGTH) -> str:
    if not value:
        return ""
    text = value.strip()
    if len(text) <= max_length:
        return text
    return text[:max_length] + "…"


def _format_attachments(attachments: Iterable[Attachment | UserAttachment]) -> str:
    lines: list[str] = []
    for attachment in attachments:
        filename = getattr(attachment, "filename", "")
        mime_type = getattr(attachment, "mime_type", None) or getattr(
            attachment, "content_type", None
        )
        description = getattr(attachment, "description", None)
        analyses = getattr(attachment, "analyses", []) or []
        analysis_description = None
        for analysis in analyses:
            analysis_description = getattr(analysis, "description", None)
            if analysis_description:
                break

        parts = [f"- {filename}"]
        if mime_type:
            parts.append(f"({mime_type})")
        if description:
            parts.append(f": {_truncate_text(description, 300)}")
        elif analysis_description:
            parts.append(f": {_truncate_text(analysis_description, 300)}")
        lines.append(" ".join(parts))

        if len(lines) >= MAX_ITEM_COUNT:
            break

    return "\n".join(lines) if lines else "нет"


def _format_link_analyses(analyses: Iterable[OrderLinkAnalysis | UserLinkAnalysis]) -> str:
    lines: list[str] = []
    for analysis in analyses:
        url = getattr(analysis, "url", "")
        payload = getattr(analysis, "analysis_json", None)
        payload_text = _format_json(payload)
        line = f"- {url}"
        if payload_text:
            line += f": {payload_text}"
        lines.append(line)
        if len(lines) >= MAX_ITEM_COUNT:
            break
    return "\n".join(lines) if lines else "нет"


def _format_json(payload) -> str:
    if not payload:
        return ""
    try:
        serialized = json.dumps(payload, ensure_ascii=False)
    except Exception:
        serialized = str(payload)
    return _truncate_text(serialized, MAX_JSON_SECTION_LENGTH)


async def generate_order_feedback(session: Session, order_id: int, user_uid: UUID) -> OrderFeedback:
    order: Order | None = session.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order with id {order_id} not found")

    user: User | None = session.query(User).filter(User.uid == user_uid).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {user_uid} not found")

    existing_feedback = (
        session.query(OrderFeedback)
        .filter(OrderFeedback.order_id == order_id, OrderFeedback.user_id == user_uid)
        .first()
    )
    if existing_feedback:
        raise HTTPException(
            status_code=400,
            detail=f"User {user_uid} already left feedback for order {order_id}",
        )

    settings = get_settings()
    if not settings.llm_api_key:
        raise HTTPException(status_code=503, detail="LLM is not configured")

    order_attachments = _format_attachments(order.attachments)
    user_attachments = _format_attachments(user.attachments)
    order_links = _format_link_analyses(order.link_analyses)
    user_links = _format_link_analyses(user.link_analyses)

    order_summary = _truncate_text(order.summary) or "нет"
    competencies = _truncate_text(user.competencies_text) or "нет"
    enriched_summary = _format_json(order.enriched_json) or "нет"

    prompt_parts = [
        "Ты — опытный фрилансер. На основе данных о заказе и профиле исполнителя нужно",
        "составить вежливый, грамотный отклик на заказ.",
        "",
        "Формат ответа: только текст отклика, без пояснений и мета-комментариев.",
        "",
        "Данные о заказе:",
        f"- Заголовок: {order.title}",
        f"- Ссылка: {order.link}",
        f"- Краткое описание: {order_summary}",
        f"- Дополнительные данные: {enriched_summary}",
        "- Вложения и их краткое описание:",
        order_attachments,
        "- Анализ ссылок по заказу:",
        order_links,
        "",
        "Данные об исполнителе:",
        f"- Компетенции: {competencies}",
        f"- Категории: {', '.join(user.categories) if user.categories else 'нет'}",
        "- Вложения и их краткое описание:",
        user_attachments,
        "- Анализ ссылок исполнителя:",
        user_links,
        "",
        "Напиши отклик, в котором:",
        "- кратко представься;",
        "- покажи, что ты понял задачу;",
        "- подчеркни релевантный опыт исполнителя;",
        "- предложи следующий шаг (уточняющие вопросы или оценку сроков/стоимости);",
        "- сохраняй дружелюбный и профессиональный тон.",
    ]

    prompt_text = "\n".join(prompt_parts)

    client = AsyncOpenAI(api_key=settings.llm_api_key)
    try:
        response = await client.responses.create(
            model=settings.openai_model,
            input=[{"role": "user", "content": prompt_text}],
            max_output_tokens=512,
        )
    except Exception as exc:  # pragma: no cover - сеть/лимиты
        logger.error(
            "Failed to generate order feedback via LLM",
            exc_info=exc,
            extra={"order_id": order_id, "user_uid": str(user_uid)},
        )
        raise HTTPException(status_code=502, detail="Failed to generate feedback")

    generated_text = _extract_response_text(response)
    if not generated_text:
        logger.warning(
            "LLM returned empty feedback",
            extra={"order_id": order_id, "user_uid": str(user_uid)},
        )
        raise HTTPException(status_code=502, detail="Failed to generate feedback")

    feedback = OrderFeedback(
        order_id=order_id,
        user_id=user_uid,
        feedback_text=generated_text,
        status="pending",
    )
    session.add(feedback)
    session.commit()
    session.refresh(feedback)

    logger.info(
        "Auto feedback generated",
        extra={"feedback_id": feedback.id, "order_id": order_id, "user_uid": str(user_uid)},
    )

    return feedback


__all__ = ["generate_order_feedback"]
