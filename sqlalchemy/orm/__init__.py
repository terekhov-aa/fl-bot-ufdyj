from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Iterator, Type, TypeVar

from .. import Condition, Connection, Engine, Metadata, Ordering

__all__ = [
    "DeclarativeBase",
    "Mapped",
    "Session",
    "joinedload",
    "mapped_column",
    "relationship",
    "sessionmaker",
]

T = TypeVar("T")


class Column:
    def __init__(
        self,
        default: Any = None,
        primary_key: bool = False,
    ) -> None:
        self.name: str | None = None
        self.default = default
        self.primary_key = primary_key

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        owner.__columns__[name] = self
        if self.primary_key:
            owner.__primary_key__ = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        if self.name is None:
            raise AttributeError("Column is not bound")
        if self.name not in instance.__dict__:
            instance.__dict__[self.name] = self._get_default()
        return instance.__dict__[self.name]

    def __set__(self, instance: Any, value: Any) -> None:
        if self.name is None:
            raise AttributeError("Column is not bound")
        instance.__dict__[self.name] = value

    # Comparisons --------------------------------------------------
    def _comparison(self, op: Callable[[Any, Any], bool], other: Any) -> Condition:
        if self.name is None:
            raise AttributeError("Column is not bound")
        return Condition(lambda obj: op(getattr(obj, self.name), other))

    def __eq__(self, other: Any) -> Condition:  # type: ignore[override]
        return self._comparison(lambda a, b: a == b, other)

    def __ne__(self, other: Any) -> Condition:  # type: ignore[override]
        return self._comparison(lambda a, b: a != b, other)

    def ilike(self, pattern: str) -> Condition:
        if self.name is None:
            raise AttributeError("Column is not bound")
        needle = pattern.replace("%", "").lower()
        return Condition(
            lambda obj: (getattr(obj, self.name) or "").lower().find(needle) != -1
        )

    def desc(self) -> Ordering:
        if self.name is None:
            raise AttributeError("Column is not bound")
        return Ordering(lambda obj: getattr(obj, self.name), True)

    def asc(self) -> Ordering:
        if self.name is None:
            raise AttributeError("Column is not bound")
        return Ordering(lambda obj: getattr(obj, self.name), False)

    def _get_default(self) -> Any:
        if callable(self.default):
            return self.default()
        return self.default


class Relationship:
    def __init__(self, *, back_populates: str | None = None) -> None:
        self.back_populates = back_populates
        self.name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        owner.__relationships__[name] = self

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        if self.name is None:
            raise AttributeError("Relationship is not bound")
        return instance.__dict__.setdefault(self.name, [])

    def __set__(self, instance: Any, value: Any) -> None:
        if self.name is None:
            raise AttributeError("Relationship is not bound")
        instance.__dict__[self.name] = value

    def any(self) -> Condition:
        if self.name is None:
            raise AttributeError("Relationship is not bound")
        return Condition(lambda obj: bool(obj.__dict__.get(self.name, [])))


def mapped_column(*_args: Any, default: Any = None, primary_key: bool = False, **_kwargs: Any) -> Column:
    return Column(default=default, primary_key=primary_key)


def relationship(*_args: Any, back_populates: str | None = None, **_kwargs: Any) -> Relationship:
    return Relationship(back_populates=back_populates)


Mapped = TypeVar("Mapped")


class DeclarativeMeta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]):
        columns: dict[str, Column] = {}
        relationships: dict[str, Relationship] = {}
        attrs.setdefault("__columns__", columns)
        attrs.setdefault("__relationships__", relationships)
        cls = super().__new__(mcls, name, bases, attrs)
        if name != "DeclarativeBase":
            DeclarativeBase.metadata.models.append(cls)
            if "__init__" not in attrs:
                cls.__init__ = mcls._create_init(columns, relationships)  # type: ignore[assignment]
        return cls

    @staticmethod
    def _create_init(columns: dict[str, Column], relationships: dict[str, Relationship]):
        def __init__(self, **kwargs: Any) -> None:
            local_kwargs = dict(kwargs)
            for column_name, column in self.__class__.__columns__.items():
                if column_name in local_kwargs:
                    value = local_kwargs.pop(column_name)
                else:
                    value = column._get_default()
                setattr(self, column_name, value)
            for rel_name, rel in self.__class__.__relationships__.items():
                if rel_name in local_kwargs:
                    setattr(self, rel_name, local_kwargs.pop(rel_name))
                else:
                    setattr(self, rel_name, [])
            for key, value in local_kwargs.items():
                setattr(self, key, value)

        return __init__


class DeclarativeBase(metaclass=DeclarativeMeta):
    metadata = Metadata()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.__columns__ = dict(getattr(cls, "__columns__", {}))
        cls.__relationships__ = dict(getattr(cls, "__relationships__", {}))


def joinedload(_relationship: Any) -> None:
    # no-op placeholder matching SQLAlchemy API
    return None


class Session:
    def __init__(self, bind: Engine | Connection | None = None):
        if bind is None:
            raise ValueError("Session requires an engine or connection bind")
        if isinstance(bind, Connection):
            self.database = bind.database
        elif isinstance(bind, Engine):
            self.database = bind.database
        else:
            raise TypeError("Unsupported bind type for Session")
        self._new: list[Any] = []

    # Basic persistence ------------------------------------------------
    def add(self, obj: Any) -> None:
        if obj not in self._new and obj not in self.database.table(obj.__class__):
            self._new.append(obj)

    def add_all(self, objects: Iterable[Any]) -> None:
        for obj in objects:
            self.add(obj)

    def flush(self) -> None:
        for obj in list(self._new):
            self._persist(obj)
        self._new.clear()

    def commit(self) -> None:
        self.flush()

    def rollback(self) -> None:
        # no transactional support in memory, so nothing to rollback
        self._new.clear()

    def close(self) -> None:
        pass

    def refresh(self, obj: Any) -> None:
        # Objects are live references; nothing required for refresh in-memory.
        return None

    def get(self, model: type, ident: Any) -> Any:
        table = self.database.table(model)
        pk_name = getattr(model, "__primary_key__", "id")
        for row in table:
            if getattr(row, pk_name, None) == ident:
                return row
        return None

    # Query helpers ----------------------------------------------------
    def scalar(self, stmt) -> Any:
        self.flush()
        results = self._run_select(stmt)
        return results[0] if results else None

    def scalars(self, stmt) -> Iterable[Any]:
        self.flush()
        return ScalarResult(self._run_select(stmt))

    def expunge_all(self) -> None:
        pass

    def execute(self, stmt) -> Iterable[Any]:
        return self.scalars(stmt)

    # Internal utilities -----------------------------------------------
    def _persist(self, obj: Any) -> None:
        table = self.database.table(obj.__class__)
        pk_name = getattr(obj.__class__, "__primary_key__", "id")
        if getattr(obj, pk_name, None) is None:
            next_id = self.database.next_ids.get(obj.__class__, 0) + 1
            self.database.next_ids[obj.__class__] = next_id
            setattr(obj, pk_name, next_id)
        if obj not in table:
            table.append(obj)
        if hasattr(obj, "created_at") and getattr(obj, "created_at") is None:
            obj.created_at = datetime.now(timezone.utc)
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at") is None:
            obj.updated_at = datetime.now(timezone.utc)
        self._sync_relationships(obj)

    def _sync_relationships(self, obj: Any) -> None:
        if hasattr(obj, "order_id"):
            order_cls = None
            for model in self.database.tables:
                if model.__name__ == "Order":
                    order_cls = model
                    break
            if order_cls is not None:
                for order in self.database.table(order_cls):
                    if getattr(order, "id", None) == getattr(obj, "order_id"):
                        attachments = order.__dict__.setdefault("attachments", [])
                        if obj not in attachments:
                            attachments.append(obj)
                        setattr(obj, "order", order)
                        break
        if hasattr(obj, "user_uid"):
            user_cls = None
            for model in self.database.tables:
                if model.__name__ == "User":
                    user_cls = model
                    break
            if user_cls is not None:
                pk_name = getattr(user_cls, "__primary_key__", "id")
                for user in self.database.table(user_cls):
                    if getattr(user, pk_name, None) == getattr(obj, "user_uid"):
                        attachments = user.__dict__.setdefault("attachments", [])
                        if obj not in attachments:
                            attachments.append(obj)
                        setattr(obj, "user", user)
                        break

    def _run_select(self, stmt) -> list[Any]:
        if hasattr(stmt, "model"):
            data = list(self.database.table(stmt.model))
            return stmt._apply(data)
        raise TypeError("Unsupported statement type")


class ScalarResult(Iterable[Any]):
    def __init__(self, results: list[Any]):
        self._results = results

    def __iter__(self) -> Iterator[Any]:
        return iter(self._results)

    def all(self) -> list[Any]:
        return list(self._results)

    def first(self) -> Any:
        return self._results[0] if self._results else None

    def one(self) -> Any:
        if len(self._results) != 1:
            raise ValueError("Expected exactly one result")
        return self._results[0]

    def one_or_none(self) -> Any:
        if not self._results:
            return None
        if len(self._results) > 1:
            raise ValueError("Expected at most one result")
        return self._results[0]
def sessionmaker(*, bind=None, class_: Type[Session] = Session, **_kwargs: Any):
    if bind is None:
        raise ValueError("sessionmaker requires a bind")
    if isinstance(bind, Connection):
        database = bind.database
    elif isinstance(bind, Engine):
        database = bind.database
    else:
        raise TypeError("sessionmaker requires an Engine or Connection bind")

    def creator(*_args: Any, **_kwargs: Any) -> Session:
        return class_(Connection(database))

    return creator
