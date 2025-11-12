from __future__ import annotations

import json
import logging
from typing import Optional

import io
from email.parser import BytesParser
from email.policy import default as email_default_policy
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from starlette.datastructures import Headers
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..db import get_session
from ..models import Attachment
from ..schemas import UploadAttachmentResponse, UploadMetadataResponse
from ..services.orders import ensure_order, update_enriched_json
from ..services.storage import save_upload_file
from ..utils.parsing import extract_external_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadMetadataResponse | UploadAttachmentResponse)
async def upload_endpoint(
    request: Request,
    session: Session = Depends(get_session),
) -> UploadMetadataResponse | UploadAttachmentResponse:
    form = await request.form()
    project_data_raw = form.get("projectData")
    type_value = form.get("type")
    upload_file = form.get("file")
    project_id = form.get("project_id") or form.get("projectId")
    page_url = form.get("page_url") or form.get("pageUrl")
    original_url = form.get("original_url") or form.get("originalUrl")
    filename = form.get("filename")

    if not project_data_raw and upload_file is None:
        body_bytes = await request.body()
        if body_bytes:
            content_type_header = request.headers.get("content-type", "")
            ctype = content_type_header.lower()
            if "multipart/form-data" in ctype:
                parsed = _parse_multipart_body(body_bytes, content_type_header)
                if project_data_raw is None:
                    value = parsed.get("projectData")
                    if isinstance(value, str):
                        project_data_raw = value
                if upload_file is None:
                    file_value = parsed.get("file")
                    if isinstance(file_value, UploadFile):
                        upload_file = file_value
                if type_value is None:
                    type_candidate = parsed.get("type")
                    if isinstance(type_candidate, str):
                        type_value = type_candidate
                if project_id is None:
                    pid_candidate = parsed.get("project_id") or parsed.get("projectId")
                    if isinstance(pid_candidate, str):
                        project_id = pid_candidate
                if page_url is None:
                    page_candidate = parsed.get("page_url") or parsed.get("pageUrl")
                    if isinstance(page_candidate, str):
                        page_url = page_candidate
                if original_url is None:
                    original_candidate = parsed.get("original_url") or parsed.get("originalUrl")
                    if isinstance(original_candidate, str):
                        original_url = original_candidate
                if filename is None:
                    filename_candidate = parsed.get("filename")
                    if isinstance(filename_candidate, str):
                        filename = filename_candidate
            elif "application/json" in ctype:
                try:
                    parsed_json = json.loads(body_bytes)
                except json.JSONDecodeError:
                    parsed_json = None
                if isinstance(parsed_json, dict):
                    if project_data_raw is None:
                        if "projectData" in parsed_json:
                            project_data_raw = json.dumps(parsed_json.get("projectData"))
                        else:
                            project_data_raw = json.dumps(parsed_json)
                    if type_value is None and parsed_json.get("type") is not None:
                        type_candidate = parsed_json.get("type")
                        if isinstance(type_candidate, str):
                            type_value = type_candidate
                    if project_id is None:
                        pid_candidate = parsed_json.get("project_id") or parsed_json.get("projectId")
                        if pid_candidate is not None:
                            project_id = str(pid_candidate)
                    if page_url is None:
                        page_candidate = parsed_json.get("page_url") or parsed_json.get("pageUrl")
                        if page_candidate is not None:
                            page_url = str(page_candidate)
                    if original_url is None:
                        original_candidate = parsed_json.get("original_url") or parsed_json.get("originalUrl")
                        if original_candidate is not None:
                            original_url = str(original_candidate)
                    if filename is None and parsed_json.get("filename") is not None:
                        filename_candidate = parsed_json.get("filename")
                        if isinstance(filename_candidate, str):
                            filename = filename_candidate
            elif "application/x-www-form-urlencoded" in ctype:
                try:
                    form_params = parse_qs(body_bytes.decode("utf-8"))
                except UnicodeDecodeError:
                    form_params = {}
                if project_data_raw is None:
                    project_data_raw = form_params.get("projectData", [None])[0]
                if type_value is None:
                    type_value = form_params.get("type", [None])[0]
                if project_id is None:
                    project_id = form_params.get("project_id", [None])[0] or form_params.get("projectId", [None])[0]
                if page_url is None:
                    page_url = form_params.get("page_url", [None])[0] or form_params.get("pageUrl", [None])[0]
                if original_url is None:
                    original_url = form_params.get("original_url", [None])[0] or form_params.get("originalUrl", [None])[0]
                if filename is None:
                    filename = form_params.get("filename", [None])[0]
            elif upload_file is None:
                try:
                    decoded = body_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    decoded = None
                if decoded:
                    fallback_params = parse_qs(decoded)
                    if project_data_raw is None:
                        project_data_raw = fallback_params.get("projectData", [None])[0]
                    if type_value is None:
                        type_value = fallback_params.get("type", [None])[0]
                    if project_id is None:
                        project_id = fallback_params.get("project_id", [None])[0] or fallback_params.get("projectId", [None])[0]
                    if page_url is None:
                        page_url = fallback_params.get("page_url", [None])[0] or fallback_params.get("pageUrl", [None])[0]
                    if original_url is None:
                        original_url = fallback_params.get("original_url", [None])[0] or fallback_params.get("originalUrl", [None])[0]
                    if filename is None:
                        filename = fallback_params.get("filename", [None])[0]
        if not project_data_raw and upload_file is None:
            raise HTTPException(status_code=400, detail="Invalid request: nothing to process")

    if upload_file is not None or type_value == "attachment":
        return await _handle_attachment(
            session,
            file=upload_file,
            project_id=project_id,
            page_url=page_url,
            original_url=original_url,
            filename=filename,
        )

    return _handle_metadata(session, project_data_raw)


def _parse_multipart_body(body: bytes, content_type: str) -> dict[str, object]:
    header = f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=email_default_policy).parsebytes(header + body)
    parsed: dict[str, object] = {}
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            headers = Headers(
                {
                    "content-disposition": part["Content-Disposition"],
                    "content-type": part.get_content_type(),
                }
            )
            upload = UploadFile(file=io.BytesIO(payload), filename=filename, headers=headers)
            parsed[name] = upload
        else:
            charset = part.get_content_charset() or "utf-8"
            parsed[name] = payload.decode(charset)
    return parsed


def _handle_metadata(session: Session, project_data_raw: str | None) -> UploadMetadataResponse:
    if not project_data_raw:
        raise HTTPException(status_code=400, detail="Invalid metadata payload")
    try:
        project_data = json.loads(project_data_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Invalid JSON in projectData") from exc

    url = project_data.get("url")
    external_id = project_data.get("id")
    external_id_int = None
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
        summary=None,
    )
    update_enriched_json(order, project_data)

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
    file: UploadFile | None,
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

    saved = await run_in_threadpool(save_upload_file, file, external_id=order.external_id, override_filename=filename)

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
    session.flush()

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
