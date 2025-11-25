from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
import httpx

from app.config import get_settings

router = APIRouter(prefix="/api/link", tags=["link-analysis"])


class LinkAnalyzeRequest(BaseModel):
    url: HttpUrl


@router.post("/analyze")
async def analyze_link(payload: LinkAnalyzeRequest):
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(settings.link_analyzer_url, json={"url": str(payload.url)})
    except httpx.RequestError as exc:  # pragma: no cover - network errors
        raise HTTPException(status_code=502, detail=f"Link analyzer is unavailable: {exc}") from exc

    if resp.status_code >= 500:
        raise HTTPException(status_code=502, detail="Link analyzer internal error")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.json())

    return resp.json()
