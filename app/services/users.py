from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..config import Settings
from ..models import User, UserAttachment
from .storage import sanitize_filename

logger = logging.getLogger(__name__)

_UNSET = object()
_DEFAULT_CHUNK_SIZE = 1024 * 1024


def normalize_categories(categories: Optional[list[str]]) -> Optional[list[str]]:
    if categories is None:
        return None
    normalized: list[str] = []
    seen: set[str] = set()
    for item in categories:
        if item is None:
            continue
        value = item.strip().lower()
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def create_user(session: Session, *, meta: Optional[dict] = None) -> User:
    user = User(uid=uuid4(), meta=meta)
    session.add(user)
    session.flush()
    logger.info("Created user", extra={"user_uid": str(user.uid)})
    return user


def update_user(
    session: Session,
    uid: UUID,
    *,
    competencies_text: object = _UNSET,
    categories: object = _UNSET,
) -> User:
    user = session.get(User, uid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if competencies_text is not _UNSET:
        user.competencies_text = competencies_text  # type: ignore[assignment]
    if categories is not _UNSET:
        normalized = normalize_categories(categories) if categories is not None else None  # type: ignore[arg-type]
        user.categories = normalized
    user.updated_at = datetime.now(UTC)
    session.flush()
    logger.info("Updated user", extra={"user_uid": str(user.uid)})
    return user


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o755)
    try:
        path.chmod(0o755)
    except PermissionError:
        pass


def _unique_filename(directory: Path, filename: str) -> Path:
    sanitized = sanitize_filename(filename or "file")
    candidate = directory / sanitized
    if not candidate.suffix and Path(filename).suffix:
        suffix = Path(filename).suffix
        stem = candidate.name
        candidate = directory / f"{stem}{suffix}"
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def save_user_upload_file(upload: UploadFile, *, uid: UUID, settings: Settings) -> dict[str, object]:
    now = datetime.now(UTC)
    base_dir = settings.upload_dir / f"user_{uid}" / f"{now.year:04d}" / f"{now.month:02d}" / f"{now.day:02d}"
    _ensure_directory(base_dir)

    original_name = upload.filename or "file"
    target_path = _unique_filename(base_dir, original_name)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    total_bytes = 0
    hasher = hashlib.sha256()

    try:
        try:
            upload.file.seek(0)
        except (AttributeError, OSError, ValueError):
            logger.debug("Upload stream is not seekable", extra={"user_uid": str(uid)})

        with target_path.open("wb") as destination:
            while True:
                chunk = upload.file.read(_DEFAULT_CHUNK_SIZE)
                if not chunk:
                    break
                destination.write(chunk)
                hasher.update(chunk)
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    destination.close()
                    target_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="Uploaded file exceeds allowed size")

        if total_bytes == 0:
            target_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        sha_hex = hasher.hexdigest()
        logger.info(
            "Saved user attachment",
            extra={
                "user_uid": str(uid),
                "path": str(target_path),
                "size_bytes": total_bytes,
                "sha256": sha_hex,
            },
        )

        return {
            "filename": target_path.name,
            "stored_path": str(target_path.resolve()),
            "size": total_bytes,
            "sha256": sha_hex,
            "content_type": upload.content_type,
        }
    finally:
        try:
            upload.file.close()
        except Exception:
            logger.debug("Failed to close upload stream", extra={"user_uid": str(uid)})


def add_user_attachments(
    session: Session,
    uid: UUID,
    uploads: Iterable[UploadFile],
    settings: Settings,
) -> list[UserAttachment]:
    user = session.get(User, uid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    created_attachments: list[UserAttachment] = []
    for upload in uploads:
        file_meta = save_user_upload_file(upload, uid=uid, settings=settings)
        attachment = UserAttachment(
            user_uid=uid,
            filename=file_meta["filename"],
            stored_path=file_meta["stored_path"],
            size=file_meta["size"],
            sha256=file_meta["sha256"],
            content_type=file_meta["content_type"],
        )
        session.add(attachment)
        created_attachments.append(attachment)

    session.flush()
    for attachment in created_attachments:
        session.refresh(attachment)
    logger.info("Added user attachments", extra={"user_uid": str(uid), "count": len(created_attachments)})
    return created_attachments


def get_user_detail(session: Session, uid: UUID) -> User:
    stmt = select(User).options(joinedload(User.attachments)).where(User.uid == uid).limit(1)
    user = session.scalar(stmt)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.attachments.sort(key=lambda item: item.created_at)
    return user
