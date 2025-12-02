from __future__ import annotations

from typing import Iterable

from ..models import Order, User


def _collect_user_links(user: User) -> list[str]:
    if not user.meta or not isinstance(user.meta, dict):
        return []
    links = user.meta.get("links", [])
    if not isinstance(links, Iterable):
        return []
    return [str(link) for link in links]


def _collect_user_attachment_descriptions(user: User) -> list[str]:
    descriptions: list[str] = []
    for attachment in user.attachments:
        meta = attachment.meta or {}
        description = meta.get("description") if isinstance(meta, dict) else None
        if description:
            descriptions.append(str(description))
    return descriptions


def _collect_order_attachment_descriptions(order: Order) -> list[str]:
    descriptions: list[str] = []
    for attachment in order.attachments:
        if attachment.description:
            descriptions.append(str(attachment.description))
    return descriptions


def generate_feedback_text(user: User, order: Order) -> str:
    """Generate a polite Russian feedback text using user and order data."""

    competencies = (user.competencies_text or "").strip()
    categories = user.categories or []
    links = _collect_user_links(user)
    user_attachment_notes = _collect_user_attachment_descriptions(user)
    order_attachment_notes = _collect_order_attachment_descriptions(order)

    intro_parts: list[str] = []
    if competencies:
        intro_parts.append(competencies)
    if categories:
        intro_parts.append(f"Основные направления: {', '.join(categories)}.")
    if links:
        intro_parts.append(f"Портфолио и проекты: {', '.join(links)}.")

    if not intro_parts:
        intro_parts.append("Готов подключиться к вашему проекту и поделиться опытом.")

    order_parts: list[str] = []
    title = order.title.strip() if order.title else ""
    summary = order.summary.strip() if order.summary else ""
    if title:
        order_parts.append(f"Заинтересовал ваш заказ \"{title}\".")
    if summary:
        order_parts.append(f"Кратко о задаче: {summary}")

    attachment_parts: list[str] = []
    if user_attachment_notes:
        attachment_parts.append(
            "Мои релевантные материалы: " + "; ".join(user_attachment_notes) + "."
        )
    elif user.attachments:
        attachment_parts.append("В профиле есть прикрепленные файлы с примерами работ.")

    if order_attachment_notes:
        attachment_parts.append(
            "Из описания заказа понял детали по вложениям: "
            + "; ".join(order_attachment_notes)
            + "."
        )

    closing = "Готов обсудить детали, сроки и стоимость, чтобы оперативно приступить к работе."

    parts = [" ".join(intro_parts)]
    if order_parts:
        parts.append(" ".join(order_parts))
    if attachment_parts:
        parts.append(" ".join(attachment_parts))
    parts.append(closing)

    return "\n\n".join(part.strip() for part in parts if part.strip())
