from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Order
from ..schemas import (
    AttachmentResponse,
    OrderAttachmentRow,
    OrderLinkAnalysisRow,
    OrderResponse,
    OrdersListResponse,
)
from ..services.orders import collect_attachments, get_order_with_attachments, list_orders as list_orders_service

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _to_order_response(order: Order) -> OrderResponse:
    attachments = [AttachmentResponse.model_validate(att) for att in collect_attachments(order)]
    return OrderResponse(
        external_id=order.external_id,
        link=order.link,
        title=order.title,
        summary=order.summary,
        pub_date=order.pub_date,
        rss_raw=order.rss_raw,
        enriched=order.enriched_json or {},
        attachments=attachments,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.get("", response_model=OrdersListResponse)
def list_orders(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None, description="Search string"),
    has_attachments: Optional[bool] = Query(None, description="Filter by attachment availability"),
) -> OrdersListResponse:
    orders = list_orders_service(session, limit=limit, offset=offset, q=q, has_attachments=has_attachments)
    items = [_to_order_response(order) for order in orders]
    return OrdersListResponse(items=items, limit=limit, offset=offset)


@router.get("/{external_id}", response_model=OrderResponse)
def get_order(external_id: int, session: Session = Depends(get_session)) -> OrderResponse:
    order = get_order_with_attachments(session, external_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return _to_order_response(order)


def _analysis_preview(payload: dict | None, *, limit: int = 1500) -> str | None:
    if payload is None:
        return None
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw) <= limit:
        return raw
    return raw[:limit] + "…"


@router.get("/{order_id}/attachments", response_model=list[OrderAttachmentRow])
def list_order_attachments(order_id: int, session: Session = Depends(get_session)) -> list[OrderAttachmentRow]:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    rows: list[OrderAttachmentRow] = []
    for attachment in order.attachments:
        ai_description: str | None = None
        if attachment.analyses:
            latest_analysis = max(attachment.analyses, key=lambda item: item.created_at)
            ai_description = latest_analysis.description

        rows.append(
            OrderAttachmentRow(
                id=attachment.id,
                filename=attachment.filename,
                mime_type=attachment.mime_type,
                description=attachment.description,
                ai_description=ai_description,
                created_at=attachment.created_at,
            )
        )

    return rows


@router.get("/{order_id}/links", response_model=list[OrderLinkAnalysisRow])
def list_order_link_analyses(order_id: int, session: Session = Depends(get_session)) -> list[OrderLinkAnalysisRow]:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    rows: list[OrderLinkAnalysisRow] = []
    for analysis in order.link_analyses:
        rows.append(
            OrderLinkAnalysisRow(
                id=analysis.id,
                url=analysis.url,
                description=analysis.description,
                analysis_json_preview=_analysis_preview(analysis.analysis_json),
                created_at=analysis.created_at,
            )
        )

    return rows
