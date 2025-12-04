from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import OrderLinkAnalysis, UserLinkAnalysis
from ..schemas import LinkDescriptionPatch, OrderLinkAnalysisRow, UserLinkAnalysisRow

router = APIRouter(prefix="/api", tags=["link-records"])


def _analysis_preview(payload: dict | None, *, limit: int = 1500) -> str | None:
    if payload is None:
        return None
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw) <= limit:
        return raw
    return raw[:limit] + "…"


@router.patch("/order-links/{analysis_id}", response_model=OrderLinkAnalysisRow)
def patch_order_link_description(
    analysis_id: int, payload: LinkDescriptionPatch, session: Session = Depends(get_session)
) -> OrderLinkAnalysisRow:
    analysis = session.get(OrderLinkAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Order link analysis not found")

    analysis.description = payload.description
    session.commit()
    session.refresh(analysis)

    return OrderLinkAnalysisRow(
        id=analysis.id,
        url=analysis.url,
        description=analysis.description,
        analysis_json_preview=_analysis_preview(analysis.analysis_json),
        created_at=analysis.created_at,
    )


@router.patch("/user-links/{analysis_id}", response_model=UserLinkAnalysisRow)
def patch_user_link_description(
    analysis_id: int, payload: LinkDescriptionPatch, session: Session = Depends(get_session)
) -> UserLinkAnalysisRow:
    analysis = session.get(UserLinkAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="User link analysis not found")

    analysis.description = payload.description
    session.commit()
    session.refresh(analysis)

    return UserLinkAnalysisRow(
        id=analysis.id,
        url=analysis.url,
        description=analysis.description,
        analysis_json_preview=_analysis_preview(analysis.analysis_json),
        created_at=analysis.created_at,
    )
