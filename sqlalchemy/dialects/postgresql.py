from __future__ import annotations

from typing import Any


class JSONB:
    def __init__(self) -> None:
        pass

    def with_variant(self, other: Any, _dialect: str) -> Any:
        return self


class ARRAY:
    def __init__(self, item_type: Any) -> None:
        self.item_type = item_type

    def with_variant(self, other: Any, _dialect: str) -> Any:
        return self


class UUID:
    def __init__(self, *, as_uuid: bool = False) -> None:
        self.as_uuid = as_uuid

    def with_variant(self, other: Any, _dialect: str) -> Any:
        return self


__all__ = ["ARRAY", "JSONB", "UUID"]
