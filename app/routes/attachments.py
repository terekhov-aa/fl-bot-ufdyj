from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Attachment
from ..schemas import AttachmentResponse

router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.get(
    "/{attachment_id}",
    response_model=AttachmentResponse,
    summary="Получить информацию о вложении",
    description=(
        "Возвращает сохраненные метаданные вложения, включая описание, "
        "которое сформировал внешний анализатор файлов."
    ),
)
def get_attachment(attachment_id: int, session: Session = Depends(get_session)) -> AttachmentResponse:
    """Возвращает информацию о вложении по его идентификатору."""

    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    return AttachmentResponse.model_validate(attachment)
