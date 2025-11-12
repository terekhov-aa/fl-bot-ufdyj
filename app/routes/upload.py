from __future__ import annotations

import inspect
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..db import get_session
from ..models import Attachment
from ..schemas import UploadAttachmentResponse, UploadMetadataResponse
from ..services.orders import ensure_order, update_enriched_json
from ..services.storage import save_upload_file
from ..utils.parsing import extract_external_id
from ..utils.multipart import parse_multipart_body

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadMetadataResponse | UploadAttachmentResponse)
async def upload_endpoint(
    request: Request,
    session: Session = Depends(get_session),
) -> UploadMetadataResponse | UploadAttachmentResponse:
    """
    Поддерживает:
    - multipart/form-data (с файлом или только полями — как в примере curl)
    - application/json
    - application/x-www-form-urlencoded
    """
    return await _dispatch_upload(request, session)


@router.post("/upload_file", response_model=UploadMetadataResponse | UploadAttachmentResponse)
async def upload_file_endpoint(
    request: Request,
    session: Session = Depends(get_session),
) -> UploadMetadataResponse | UploadAttachmentResponse:
    """
    Полный алиас /api/upload — нужен для клиентов, которые шлют на /api/upload_file.
    """
    return await _dispatch_upload(request, session)


async def _dispatch_upload(
    request: Request,
    session: Session,
) -> UploadMetadataResponse | UploadAttachmentResponse:
    ctype = (request.headers.get("content-type") or "").lower()

    # Нормализованные переменные (заполняем ниже из формы/тела)
    file: Optional[UploadFile] = None
    project_data_raw: Optional[str] = None
    project_id: Optional[str] = None
    page_url: Optional[str] = None
    original_url: Optional[str] = None
    filename: Optional[str] = None
    type_value: Optional[str] = None

    if "multipart/form-data" in ctype:
        # 1) Пытаемся штатно прочитать форму
        form = None
        try:
            form = await request.form()
        except Exception as e:
            logger.warning("request.form() failed, will fallback to manual multipart parse: %s", e)

        if form is not None:
            project_data_raw = form.get("projectData")
            type_value = ((form.get("type") or "").strip().lower()) if form.get("type") else None
            project_id = form.get("project_id") or form.get("projectId")
            page_url = form.get("page_url") or form.get("pageUrl")
            original_url = form.get("original_url") or form.get("originalUrl")
            filename = form.get("filename")
            maybe_file = form.get("file")
            if isinstance(maybe_file, UploadFile):
                file = maybe_file

        # 2) Если из формы ничего не получили (или форм-парсер недоступен) — парсим multipart вручную
        if project_data_raw is None and file is None:
            body = await request.body()
            if body:
                parsed = parse_multipart_body(body, request.headers.get("content-type", ""))
                val = parsed.get("projectData")
                if isinstance(val, str):
                    project_data_raw = val
                # опциональные параметры
                t = parsed.get("type")
                if isinstance(t, str):
                    type_value = t.strip().lower()
                pid = parsed.get("project_id") or parsed.get("projectId")
                if isinstance(pid, str):
                    project_id = pid
                pg = parsed.get("page_url") or parsed.get("pageUrl")
                if isinstance(pg, str):
                    page_url = pg
                ou = parsed.get("original_url") or parsed.get("originalUrl")
                if isinstance(ou, str):
                    original_url = ou
                fn = parsed.get("filename")
                if isinstance(fn, str):
                    filename = fn
                fv = parsed.get("file")
                if isinstance(fv, list):
                    fv = next((item for item in fv if isinstance(item, UploadFile)), None)
                if isinstance(fv, UploadFile):
                    file = fv

    elif "application/json" in ctype:
        try:
            data = await request.json()
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid JSON in request body")

        # Не «двойное» кодирование projectData
        pd = data.get("projectData", data)
        if isinstance(pd, (dict, list)):
            project_data_raw = json.dumps(pd, ensure_ascii=False)
        elif isinstance(pd, str):
            project_data_raw = pd
        else:
            raise HTTPException(status_code=422, detail="projectData must be object/array or JSON string")

        pid = data.get("project_id") or data.get("projectId")
        project_id = str(pid) if pid is not None else None
        page_url = data.get("page_url") or data.get("pageUrl")
        original_url = data.get("original_url") or data.get("originalUrl")
        filename = data.get("filename")
        tv = data.get("type")
        type_value = (tv or "").strip().lower() if tv is not None else None

    else:
        # URL-encoded фолбэк
        from urllib.parse import parse_qs
        try:
            params = parse_qs((await request.body()).decode("utf-8"))
        except Exception:
            params = {}
        project_data_raw = params.get("projectData", [None])[0]
        tv = params.get("type", [None])[0]
        type_value = (tv or "").strip().lower() if tv else None
        project_id = (params.get("project_id", [None])[0]
                      or params.get("projectId", [None])[0])
        page_url = (params.get("page_url", [None])[0]
                    or params.get("pageUrl", [None])[0])
        original_url = (params.get("original_url", [None])[0]
                        or params.get("originalUrl", [None])[0])
        filename = params.get("filename", [None])[0]

    # Ветвление по режиму
    if file is not None or type_value == "attachment":
        return await _handle_attachment(
            session,
            file=file,
            project_id=project_id,
            page_url=page_url,
            original_url=original_url,
            filename=filename,
        )

    if project_data_raw:
        return _handle_metadata(session, project_data_raw)

    raise HTTPException(status_code=400, detail="Invalid request: nothing to process")

def _handle_metadata(session: Session, project_data_raw: str) -> UploadMetadataResponse:
    if not project_data_raw:
        raise HTTPException(status_code=400, detail="Invalid metadata payload")
    try:
        project_data = json.loads(project_data_raw)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in projectData: %s", exc)
        raise HTTPException(status_code=422, detail="Invalid JSON in projectData") from exc

    url = project_data.get("url")
    external_id = project_data.get("id")

    if isinstance(external_id, int):
        external_id_int = external_id
    elif isinstance(external_id, str) and external_id.isdigit():
        external_id_int = int(external_id)
    else:
        external_id_int = extract_external_id(url)

    order = ensure_order(
        session,
        external_id=external_id_int,
        link=url,
        title=project_data.get("title") or "",
        summary=project_data.get("summary"),
    )
    update_enriched_json(order, project_data)
    session.commit()

    logger.info("Metadata uploaded", extra={"external_id": order.external_id, "order_id": order.id})

    return UploadMetadataResponse(
        status="success",
        mode="metadata",
        order={
            "external_id": order.external_id,
            "id": order.id,
            "link": order.link,
        },
    )


async def _handle_attachment(
    session: Session,
    *,
    file: Optional[UploadFile],
    project_id: Optional[str],
    page_url: Optional[str],
    original_url: Optional[str],
    filename: Optional[str],
) -> UploadAttachmentResponse:
    if file is None:
        raise HTTPException(status_code=400, detail="Attachment file is required")

    external_id: Optional[int] = None
    if project_id and project_id.isdigit():
        external_id = int(project_id)
    if external_id is None:
        external_id = extract_external_id(page_url) or extract_external_id(original_url)

    link = page_url or original_url
    order = ensure_order(session, external_id=external_id, link=link, title="", summary=None)

    # Совместимый вызов: если save_upload_file асинхронная — просто await,
    # если синхронная — уводим в threadpool.
    if inspect.iscoroutinefunction(save_upload_file):
        saved = await save_upload_file(  # type: ignore[misc]
            file,
            external_id=order.external_id,
            override_filename=filename,
        )
    else:
        saved = await run_in_threadpool(
            save_upload_file,
            file,
            external_id=order.external_id,
            override_filename=filename,
        )

    attachment = Attachment(
        order_id=order.id,
        filename=saved["filename"],
        stored_path=saved["stored_path"],
        size_bytes=int(saved["size_bytes"]),
        mime_type=saved.get("mime_type"),
        original_url=original_url,
        page_url=page_url,
        sha256=saved.get("sha256"),
    )
    session.add(attachment)
    session.commit()

    logger.info(
        "Attachment uploaded",
        extra={"attachment_id": attachment.id, "order_id": order.id, "external_id": order.external_id},
    )

    return UploadAttachmentResponse(
        status="success",
        mode="attachment",
        file={
            "filename": attachment.filename,
            "size_bytes": attachment.size_bytes,
            "sha256": attachment.sha256,
        },
        order={
            "external_id": order.external_id,
            "id": order.id,
        },
    )
