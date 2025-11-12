from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from ..config import Settings, get_settings
from ..db import get_session
from ..schemas import UserAttachmentOut, UserCreateResponse, UserDetail, UserPatch
from ..services import users as users_service
from ..utils.multipart import parse_multipart_body

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post(
    "/",
    response_model=UserCreateResponse,
    summary="Create user profile",
    description=(
            "Create a new user profile and return the generated UID. Optionally accepts "
            "a `meta` object with arbitrary JSON data."
    ),
)
def create_user_endpoint(
        payload: dict[str, Any] | None = Body(default=None),
        session: Session = Depends(get_session),
) -> UserCreateResponse:
    meta: dict[str, Any] | None = None
    if payload is not None:
        meta_value = payload.get("meta")
        if meta_value is not None and not isinstance(meta_value, dict):
            raise HTTPException(status_code=400, detail="meta must be an object")
        meta = meta_value
    user = users_service.create_user(session, meta=meta)
    logger.info("Created user via API", extra={"user_uid": str(user.uid)})
    return UserCreateResponse(uid=user.uid)


@router.get(
    "/{uid}",
    response_model=UserDetail,
    summary="Get user profile",
    description="Return a user profile along with all uploaded attachments.",
)
def get_user_endpoint(
        uid: UUID,
        session: Session = Depends(get_session),
) -> UserDetail:
    user = users_service.get_user_detail(session, uid)
    logger.info("Fetched user", extra={"user_uid": str(uid)})
    return UserDetail.model_validate(user, from_attributes=True)


@router.patch(
    "/{uid}",
    response_model=UserDetail,
    summary="Update user profile",
    description=(
            "Update the user's competencies text and categories. Categories are "
            "normalized to lower case without duplicates."
    ),
)
def patch_user_endpoint(
        uid: UUID,
        payload: UserPatch,
        session: Session = Depends(get_session),
) -> UserDetail:
    data = payload.model_dump(exclude_unset=True)
    update_kwargs: dict[str, Any] = {}
    if "competencies_text" in data:
        update_kwargs["competencies_text"] = data["competencies_text"]
    if "categories" in data:
        update_kwargs["categories"] = data["categories"]
    users_service.update_user(session, uid, **update_kwargs)
    user = users_service.get_user_detail(session, uid)
    logger.info("Updated user via API", extra={"user_uid": str(uid)})
    return UserDetail.model_validate(user, from_attributes=True)


@router.post(
    "/{uid}/files",
    response_model=list[UserAttachmentOut],
    summary="Upload user files",
    description=(
            "Upload one or more files (portfolio, resume) for the specified user. "
            "The endpoint accepts form fields named either `files` or `files[]` and "
            "saves them using the standard upload rules with hashing and size checks."
    ),
)
async def upload_user_files_endpoint(
        uid: UUID,
        request: Request,
        session: Session = Depends(get_session),
        settings: Settings = Depends(get_settings),
) -> list[UserAttachmentOut]:
    uploads = await _extract_uploads_from_request(request)
    if not uploads:
        raise HTTPException(status_code=400, detail="No files uploaded")

    attachments = users_service.add_user_attachments(session, uid, uploads, settings)
    logger.info("Uploaded user files", extra={"user_uid": str(uid), "count": len(attachments)})
    return [UserAttachmentOut.model_validate(item, from_attributes=True) for item in attachments]


@router.post("/_debug/echo-multipart")
async def echo_multipart_debug_endpoint(
        request: Request,
) -> list[dict[str, int | str]]:
    uploads = await _extract_uploads_from_request(request)
    response: list[dict[str, int | str]] = []
    for upload in uploads:
        content = await upload.read()
        response.append({
            "name": upload.filename,
            "size": len(content),
        })
        await upload.seek(0)
    return response


async def _extract_uploads_from_request(request: Request) -> list[UploadFile]:
    """Return uploaded files handling both ``files`` and ``files[]`` field names."""

    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" not in content_type:
        return []

    uploads: list[UploadFile] = []
    form: FormData | None = None

    try:
        form = await request.form()
    except Exception as exc:  # pragma: no cover - logging aid
        logger.warning("request.form() failed for user upload: %s", exc)

    if form is not None:
        uploads.extend(_uploads_from_form(form, "files"))
        uploads.extend(_uploads_from_form(form, "files[]"))
        if uploads:
            return uploads

    body = await request.body()
    if not body:
        return []

    parsed = parse_multipart_body(body, request.headers.get("content-type", ""))
    uploads.extend(_uploads_from_mapping(parsed, "files"))
    uploads.extend(_uploads_from_mapping(parsed, "files[]"))

    if uploads and form is not None:
        logger.debug("Used fallback multipart parser for user upload; request.form() returned no files")

    return uploads


def _uploads_from_form(form: FormData, key: str) -> list[UploadFile]:
    values = form.getlist(key) if hasattr(form, "getlist") else []
    return [item for item in values if isinstance(item, UploadFile)]


def _uploads_from_mapping(parsed: dict[str, Any], key: str) -> list[UploadFile]:
    value = parsed.get(key)
    if isinstance(value, UploadFile):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, UploadFile)]
    return []
