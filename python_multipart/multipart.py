from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable

Callbacks = Dict[str, Callable]


def parse_options_header(value: bytes | str) -> tuple[str, dict[bytes, bytes]]:
    if isinstance(value, bytes):
        text = value.decode("latin-1")
    else:
        text = value
    parts = [part.strip() for part in text.split(";")]
    main = parts[0] if parts else ""
    params: dict[bytes, bytes] = {}
    for item in parts[1:]:
        if not item or "=" not in item:
            continue
        key, val = item.split("=", 1)
        key_bytes = key.strip().lower().encode("latin-1")
        cleaned = val.strip().strip('"')
        params[key_bytes] = cleaned.encode("latin-1")
    return main, params


class QuerystringParser:
    def __init__(self, callbacks: Callbacks) -> None:
        self.callbacks = callbacks
        self._buffer = bytearray()

    def write(self, data: bytes) -> None:
        # Parsing URL-encoded chunks as they arrive
        self._buffer.extend(data)
        self._emit_pairs(finalize=False)

    def finalize(self) -> None:
        self._emit_pairs(finalize=True)

    def _emit_pairs(self, finalize: bool) -> None:
        payload = bytes(self._buffer)
        if not payload:
            if finalize:
                self.callbacks.get("on_end", lambda: None)()
            return
        # Debugging prints can be replaced by logging if needed
        # Emit accumulated key-value pairs
        for pair in payload.split(b"&"):
            if not pair:
                continue
            name, _, value = pair.partition(b"=")
            self.callbacks.get("on_field_start", lambda: None)()
            self.callbacks.get("on_field_name", lambda data, start, end: None)(name, 0, len(name))
            self.callbacks.get("on_field_data", lambda data, start, end: None)(value, 0, len(value))
            self.callbacks.get("on_field_end", lambda: None)()
        self._buffer.clear()
        self.callbacks.get("on_end", lambda: None)()


@dataclass
class _Part:
    headers: list[tuple[bytes, bytes]]
    body: bytes


class MultipartParser:
    def __init__(self, boundary: bytes | str, callbacks: Callbacks) -> None:
        if isinstance(boundary, str):
            boundary = boundary.encode("latin-1")
        self.boundary = boundary
        self.callbacks = callbacks
        self._buffer = bytearray()

    def write(self, data: bytes) -> None:
        self._buffer.extend(data)

    def finalize(self) -> None:
        data = bytes(self._buffer)
        boundary = b"--" + self.boundary
        if boundary not in data:
            return
        sections = data.split(boundary)
        for section in sections:
            if not section or section == b"--" or section == b"--\r\n":
                continue
            chunk = section.strip(b"\r\n")
            if chunk == b"--":
                continue
            header_bytes, _, body = chunk.partition(b"\r\n\r\n")
            headers: list[tuple[bytes, bytes]] = []
            for line in header_bytes.split(b"\r\n"):
                if not line:
                    continue
                name, _, value = line.partition(b":")
                headers.append((name.strip(), value.strip()))
            part = _Part(headers=headers, body=body)
            self._emit_part(part)
        self.callbacks.get("on_end", lambda: None)()

    def _emit_part(self, part: _Part) -> None:
        callbacks = self.callbacks
        callbacks.get("on_part_begin", lambda: None)()
        for name, value in part.headers:
            callbacks.get("on_header_field", lambda data, start, end: None)(name, 0, len(name))
            callbacks.get("on_header_value", lambda data, start, end: None)(value, 0, len(value))
            callbacks.get("on_header_end", lambda: None)()
        callbacks.get("on_headers_finished", lambda: None)()
        callbacks.get("on_part_data", lambda data, start, end: None)(part.body, 0, len(part.body))
        callbacks.get("on_part_end", lambda: None)()
