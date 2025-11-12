from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from ..config import RSSIngestOptions
from ..db import get_session
from ..rss import ingest_rss
from ..schemas import RSSIngestRequest, RSSIngestResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rss", tags=["rss"])


@router.post("/ingest", response_model=RSSIngestResponse)
def ingest_endpoint(payload: RSSIngestRequest, session=Depends(get_session)) -> RSSIngestResponse:
    options = RSSIngestOptions(**payload.model_dump(exclude_none=True))
    inserted, updated = ingest_rss(session, options)
    return RSSIngestResponse(status="ok", inserted=inserted, updated=updated)
