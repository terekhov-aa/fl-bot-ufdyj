from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

from ..config import get_settings

logger = logging.getLogger(__name__)

SAFE_CHARS_PATTERN = re.compile(r"[^A-Za-z0-9._-]+", re.UNICODE)


def sanitize_filename(name: str) -> str:
    """Очищает имя файла от небезопасных символов"""
    base_name = Path(name).name
    sanitized = SAFE_CHARS_PATTERN.sub("_", base_name)
    return sanitized or "file"


def ensure_unique_path(path: Path) -> Path:
    """Генерирует уникальный путь если файл уже существует"""
    if not path.exists():
        return path
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    random_suffix = secrets.token_hex(4)
    new_name = f"{path.stem}__{timestamp}_{random_suffix}{path.suffix}"
    return path.with_name(new_name)


async def save_upload_file(
    upload: UploadFile,
    *,
    external_id: Optional[int],
    override_filename: Optional[str] = None,
) -> dict[str, str | int | None]:
    """
    Асинхронно сохраняет загруженный файл.
    
    Args:
        upload: Загруженный файл
        external_id: ID внешнего заказа
        override_filename: Переопределить имя файла
        
    Returns:
        Словарь с информацией о сохраненном файле
    """
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024

    filename = override_filename or upload.filename or "file"
    filename = sanitize_filename(filename)

    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Создаем структуру директорий
    now = datetime.now(UTC)
    project_segment = f"project_{external_id}" if external_id is not None else "project_unknown"
    target_dir = settings.upload_dir / project_segment / f"{now.year:04d}" / f"{now.month:02d}" / f"{now.day:02d}"
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
    
    try:
        target_dir.chmod(0o755)
    except PermissionError:
        # Игнорируем ошибки прав доступа (например, на примонтированных томах)
        pass

    target_path = ensure_unique_path(target_dir / filename)

    # Сохраняем файл и вычисляем хеш
    hasher = hashlib.sha256()
    total_bytes = 0

    try:
        with target_path.open("wb") as out_file:
            # Сбрасываем позицию чтения файла на начало
            await upload.seek(0)
            
            while True:
                # Асинхронное чтение чанками
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                    
                total_bytes += len(chunk)
                
                # Проверка размера файла
                if total_bytes > max_bytes:
                    out_file.close()
                    target_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413, 
                        detail=f"Uploaded file exceeds allowed size ({settings.max_upload_mb}MB)"
                    )
                
                hasher.update(chunk)
                out_file.write(chunk)

        if total_bytes == 0:
            target_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        sha256_hash = hasher.hexdigest()
        
        logger.info(
            "Saved attachment",
            extra={
                "external_id": external_id,
                "path": str(target_path),
                "size_bytes": total_bytes,
                "sha256": sha256_hash,
            },
        )

        return {
            "filename": target_path.name,
            "stored_path": str(target_path.resolve()),
            "size_bytes": total_bytes,
            "sha256": sha256_hash,
            "mime_type": upload.content_type,
        }
        
    except Exception as e:
        # Удаляем частично загруженный файл в случае ошибки
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        
        if isinstance(e, HTTPException):
            raise
        
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
