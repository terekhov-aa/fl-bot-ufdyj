from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

router = APIRouter(prefix="/api/link", tags=["link-analysis"])


class LinkAnalyzeRequest(BaseModel):
    url: HttpUrl


@router.post("/analyze")
async def analyze_link(payload: LinkAnalyzeRequest):
    # Внешний сервис link_analyzer отключён. Эндпоинт оставлен только для совместимости.
    raise HTTPException(status_code=503, detail="Link analyzer service is disabled")
