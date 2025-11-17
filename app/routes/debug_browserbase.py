from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ..services.debug_stagehand import analyze_page_with_stagehand

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/browserbase")
async def debug_browserbase(url: str = Query(..., description="URL, который нужно открыть через Browserbase")) -> JSONResponse:
    result = await analyze_page_with_stagehand(url)

    if result.get("success"):
        return JSONResponse(
            content={
                "success": True,
                "url": result.get("url", url),
                "description": result.get("description"),
            }
        )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "url": result.get("url", url),
            "error": result.get("error"),
        },
    )
