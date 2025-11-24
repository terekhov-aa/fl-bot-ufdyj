from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.link_analyzer import LinkAnalyzeRequest, LinkAnalysisResult, analyze_link

router = APIRouter(prefix="/api/link", tags=["links"])


@router.post("/analyze", response_model=LinkAnalysisResult, summary="Analyze external link")
async def analyze_external_link(body: LinkAnalyzeRequest) -> LinkAnalysisResult:
    """Send a public URL to the link analyzer service and return the structured result."""

    result = await analyze_link(body.url)
    if result is None:
        raise HTTPException(status_code=503, detail="Link analyzer is unavailable")
    return result
