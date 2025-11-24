from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
from pydantic import BaseModel, HttpUrl, Field

from app.config import get_settings

logger = logging.getLogger(__name__)


class ParsedLink(BaseModel):
    url: HttpUrl | str
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    statusCode: Optional[int] = Field(default=None, alias="statusCode")
    contentLength: Optional[int] = Field(default=None, alias="contentLength")
    textPreview: Optional[str] = None

    model_config = dict(populate_by_name=True)


class ProjectInfo(BaseModel):
    projectType: str = ""
    summary: str = ""
    targetAudience: str = ""
    mainFlows: list[str] = Field(default_factory=list)
    mainFeatures: list[str] = Field(default_factory=list)
    techStackGuess: list[str] = Field(default_factory=list)
    complexity: str = "unknown"
    risks: list[str] = Field(default_factory=list)
    tasksForFreelancer: list[str] = Field(default_factory=list)


class LinkAnalysisResult(BaseModel):
    success: bool
    contentType: str
    analysisMode: str
    parsed: Optional[ParsedLink] = None
    projectInfo: Optional[ProjectInfo] = None
    limitations: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class LinkAnalyzeRequest(BaseModel):
    url: HttpUrl = Field(..., description="Public URL to analyze")


async def analyze_link(url: str) -> Optional[LinkAnalysisResult]:
    settings = get_settings()
    if not settings.link_analyzer_url:
        logger.warning("LINK_ANALYZER_URL is not configured; skipping external analysis")
        return None

    payload: dict[str, Any] = {"url": url}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(settings.link_analyzer_url, json=payload)
            response.raise_for_status()
            data = response.json()
            return LinkAnalysisResult.model_validate(data)
    except httpx.HTTPStatusError as exc:
        logger.error("Link analyzer responded with status %s: %s", exc.response.status_code, exc)
    except httpx.HTTPError as exc:
        logger.error("Failed to reach link analyzer: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error calling link analyzer: %s", exc)
    return None
