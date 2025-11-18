from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

from app.schemas import ParseSiteRequest, ParseSiteResponse
from app.services import stagehand_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["stagehand"])


def _is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return all([parsed.scheme in {"http", "https"}, parsed.netloc])


@router.post("/parse-site", response_model=ParseSiteResponse)
async def parse_site_endpoint(payload: ParseSiteRequest) -> ParseSiteResponse:
    if not payload.url or not _is_valid_url(payload.url):
        raise HTTPException(status_code=400, detail="A valid http(s) URL is required")

    try:
        result = await stagehand_client.parse_site(
            payload.url,
            instruction=payload.instruction,
            schema=payload.schema_,
            options=payload.options,
        )
    except stagehand_client.StagehandServiceError as exc:
        logger.error("Stagehand service error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - unexpected
        logger.exception("Unexpected error while parsing site")
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    return ParseSiteResponse(result=result.get("result", result))
