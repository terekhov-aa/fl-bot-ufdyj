from __future__ import annotations

import io
from email.parser import BytesParser
from email.policy import default as email_default_policy
from typing import Any

from fastapi import UploadFile
from starlette.datastructures import Headers


def parse_multipart_body(body: bytes, content_type_header: str) -> dict[str, Any]:
    """Parse a multipart/form-data payload without relying on python-multipart.

    The implementation mirrors the fallback logic that existed in the legacy
    upload routes. It returns a mapping where every key can contain either a
    single value (``str`` or ``UploadFile``) or a list with multiple entries.
    """

    header = f"Content-Type: {content_type_header}\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=email_default_policy).parsebytes(header + body)
    parsed: dict[str, Any] = {}

    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue

        name = part.get_param("name", header="content-disposition")
        if not name:
            continue

        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""

        existing = parsed.get(name)

        if filename:
            headers = Headers(
                {
                    "content-disposition": part["Content-Disposition"],
                    "content-type": part.get_content_type(),
                }
            )
            upload = UploadFile(file=io.BytesIO(payload), filename=filename, headers=headers)

            if existing is None:
                parsed[name] = upload
            elif isinstance(existing, list):
                existing.append(upload)
            else:
                parsed[name] = [existing, upload]

            continue

        charset = part.get_content_charset() or "utf-8"
        text_value = payload.decode(charset, errors="ignore")

        if existing is None:
            parsed[name] = text_value
        elif isinstance(existing, list):
            existing.append(text_value)
        else:
            parsed[name] = [existing, text_value]

    return parsed

