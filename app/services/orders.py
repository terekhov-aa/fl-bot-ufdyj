from __future__ import annotations

import logging
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, joinedload

from ..models import Attachment, Order
from ..utils.time import ensure_utc

logger = logging.getLogger(__name__)


def deep_merge_dicts(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = deepcopy(base) if base else {}
    for key, value in incoming.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def _build_lookup_clause(external_id: Optional[int], link: str):
    if external_id is not None:
        return or_(Order.external_id == external_id, Order.link == link)
    return Order.link == link


def upsert_order_from_rss(
    session: Session,
    *,
    external_id: Optional[int],
    link: str,
    title: str,
    summary: Optional[str],
    pub_date: Optional[datetime],
    rss_raw: dict[str, Any],
) -> tuple[Order, bool]:
    stmt: Select[tuple[Order]] = select(Order).where(_build_lookup_clause(external_id, link)).limit(1)
    order = session.scalar(stmt)
    created = False
    if order is None:
        order = Order(
            external_id=external_id,
            link=link,
            title=title,
            summary=summary,
            pub_date=ensure_utc(pub_date),
            rss_raw=rss_raw,
        )
        session.add(order)
        created = True
        logger.info("Inserted order", extra={"external_id": external_id, "link": link})
    else:
        order.title = title
        order.summary = summary
        order.pub_date = ensure_utc(pub_date)
        order.rss_raw = rss_raw
        if external_id is not None and order.external_id is None:
            order.external_id = external_id
        order.updated_at = datetime.now(UTC)
        logger.info("Updated order", extra={"order_id": order.id, "external_id": order.external_id, "link": link})
    return order, created


def ensure_order(
    session: Session,
    *,
    external_id: Optional[int],
    link: Optional[str],
    title: Optional[str] = None,
    summary: Optional[str] = None,
    rss_raw: Optional[dict[str, Any]] = None,
) -> Order:
    order: Order | None = None
    if external_id is not None:
        order = session.scalar(select(Order).where(Order.external_id == external_id).limit(1))
    if order is None and link:
        order = session.scalar(select(Order).where(Order.link == link).limit(1))
    if order is None:
        order = Order(
            external_id=external_id,
            link=link or f"unknown://{datetime.utcnow().timestamp()}",
            title=title or "",
            summary=summary,
            rss_raw=rss_raw or {},
        )
        session.add(order)
        session.flush()
        logger.info("Created placeholder order", extra={"order_id": order.id, "external_id": external_id, "link": order.link})
    return order


def update_enriched_json(order: Order, payload: dict[str, Any]) -> None:
    order.enriched_json = deep_merge_dicts(order.enriched_json or {}, payload)


def get_order_with_attachments(session: Session, external_id: int) -> Order | None:
    stmt = (
        select(Order)
        .options(joinedload(Order.attachments))
        .where(Order.external_id == external_id)
        .limit(1)
    )
    return session.scalar(stmt)


def list_orders(
    session: Session,
    *,
    limit: int,
    offset: int,
    q: Optional[str] = None,
    has_attachments: Optional[bool] = None,
) -> list[Order]:
    stmt = select(Order).options(joinedload(Order.attachments)).order_by(Order.updated_at.desc())
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Order.title.ilike(pattern), Order.summary.ilike(pattern)))
    if has_attachments is not None:
        if has_attachments:
            stmt = stmt.where(Order.attachments.any())
        else:
            stmt = stmt.where(~Order.attachments.any())
    stmt = stmt.offset(offset).limit(limit)
    return list(session.scalars(stmt))


def collect_attachments(order: Order) -> list[Attachment]:
    return list(order.attachments)
