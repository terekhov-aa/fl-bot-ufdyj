from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional, Sequence

__all__ = [
    "BigInteger",
    "DateTime",
    "ForeignKey",
    "JSON",
    "Select",
    "Text",
    "create_engine",
    "func",
    "or_",
    "select",
]


class _Type:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"Type({self.name})"


class BigInteger(_Type):
    def __init__(self) -> None:
        super().__init__("BIGINT")


class DateTime(_Type):
    def __init__(self, timezone: bool = False) -> None:
        super().__init__("TIMESTAMP WITH TIME ZONE" if timezone else "TIMESTAMP")
        self.timezone = timezone


class Text(_Type):
    def __init__(self) -> None:
        super().__init__("TEXT")


class String(_Type):
    def __init__(self, length: int | None = None) -> None:
        suffix = f"({length})" if length is not None else ""
        super().__init__(f"VARCHAR{suffix}")
        self.length = length


class JSON(_Type):
    def __init__(self) -> None:
        super().__init__("JSON")


class ForeignKey:
    def __init__(self, target: str, ondelete: Optional[str] = None) -> None:
        self.target = target
        self.ondelete = ondelete


class func:
    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)


class Condition:
    def __init__(self, predicate: Callable[[Any], bool]) -> None:
        self._predicate = predicate

    def evaluate(self, obj: Any) -> bool:
        return self._predicate(obj)

    def __and__(self, other: "Condition") -> "Condition":
        return Condition(lambda obj: self.evaluate(obj) and other.evaluate(obj))

    def __or__(self, other: "Condition") -> "Condition":
        return Condition(lambda obj: self.evaluate(obj) or other.evaluate(obj))

    def __invert__(self) -> "Condition":
        return Condition(lambda obj: not self.evaluate(obj))


def or_(*conditions: Condition) -> Condition:
    return Condition(lambda obj: any(cond.evaluate(obj) for cond in conditions))


class Ordering:
    def __init__(self, getter: Callable[[Any], Any], descending: bool) -> None:
        self.getter = getter
        self.descending = descending


class Select:
    def __init__(self, model: type):
        self.model = model
        self._conditions: list[Condition] = []
        self._limit: Optional[int] = None
        self._offset: int = 0
        self._orderings: list[Ordering] = []

    def where(self, condition: Condition) -> "Select":
        self._conditions.append(condition)
        return self

    def limit(self, value: int) -> "Select":
        self._limit = value
        return self

    def offset(self, value: int) -> "Select":
        self._offset = value
        return self

    def order_by(self, *orderings: Ordering) -> "Select":
        self._orderings.extend(orderings)
        return self

    def options(self, *unused: Any) -> "Select":
        # options such as joinedload are no-ops in this lightweight implementation
        return self

    # Internal helpers -------------------------------------------------
    def _apply(self, items: Sequence[Any]) -> list[Any]:
        filtered: Iterable[Any] = items
        for cond in self._conditions:
            filtered = [obj for obj in filtered if cond.evaluate(obj)]
        result = list(filtered)
        if self._orderings:
            for ordering in reversed(self._orderings):
                result.sort(key=ordering.getter, reverse=ordering.descending)
        if self._offset:
            result = result[self._offset :]
        if self._limit is not None:
            result = result[: self._limit]
        return result


def select(model: type) -> Select:
    return Select(model)


# ----------------------- Simple in-memory database --------------------


class Database:
    def __init__(self) -> None:
        self.tables: dict[type, list[Any]] = {}
        self.next_ids: dict[type, int] = {}

    def table(self, model: type) -> list[Any]:
        return self.tables.setdefault(model, [])

    def clear(self) -> None:
        self.tables.clear()
        self.next_ids.clear()


_DATABASES: dict[str, Database] = {}


class Engine:
    def __init__(self, url: str):
        self.url = url
        self.database = _DATABASES.setdefault(url, Database())

    def connect(self) -> "Connection":
        return Connection(self.database)

    def dispose(self) -> None:
        # nothing to dispose in memory
        pass


class Connection:
    def __init__(self, database: Database) -> None:
        self.database = database

    def begin(self) -> "Transaction":
        return Transaction()

    def close(self) -> None:
        pass


class Transaction:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def create_engine(url: str, **_: Any) -> Engine:
    return Engine(url)


# Metadata helpers -----------------------------------------------------


class Metadata:
    def __init__(self) -> None:
        self.models: list[type] = []

    def create_all(self, engine: Engine) -> None:
        # ensure tables exist
        for model in self.models:
            engine.database.table(model)

    def drop_all(self, engine: Engine) -> None:
        engine.database.clear()


from .orm import DeclarativeBase, Session, sessionmaker

__all__.extend(["DeclarativeBase", "Session", "sessionmaker", "Metadata"])
