from __future__ import annotations

from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import AliasChoices, AnyHttpUrl, BaseModel, ConfigDict, Field

from ..config import Settings, get_settings

router = APIRouter(prefix="/api/parse", tags=["stagehand"])


class ParseRequest(BaseModel):
    """Incoming request payload for triggering Stagehand parsing."""

    model_config = ConfigDict(populate_by_name=True)

    url: AnyHttpUrl = Field(
        validation_alias=AliasChoices("url", "site"),
        description="Target website URL",
    )


@router.post("", summary="Parse a webpage using the Stagehand service")
def parse_site(
    payload: ParseRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Proxy parse requests through the Node/Stagehand service."""

    try:
        response = requests.post(
            f"{settings.stagehand_service_url}/parse",
            json={"url": str(payload.url)},
            timeout=60,
        )
    except requests.RequestException as exc:  # pragma: no cover - network handling
        raise HTTPException(status_code=502, detail="Stagehand service unavailable") from exc

    try:
        data = response.json()
    except ValueError as exc:  # pragma: no cover - defensive check
        raise HTTPException(status_code=502, detail="Invalid response from Stagehand service") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data.get("error") or "Stagehand request failed")

    if not data.get("success", False):
        raise HTTPException(status_code=502, detail=data.get("error") or "Stagehand responded with failure")

    # Keep the payload consistent for the caller: client -> Python -> Node -> Python -> client
    return data
