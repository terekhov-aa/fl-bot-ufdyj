from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY as PGARRAY
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON

from .db import Base

JSONBType = PGJSONB().with_variant(JSON(), "sqlite")
UUIDType = PGUUID(as_uuid=True).with_variant(String(36), "sqlite")
CategoriesType = PGARRAY(Text).with_variant(JSON(), "sqlite")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    link: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    pub_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rss_raw: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    enriched_json: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now(), nullable=False)

    attachments: Mapped[list[Attachment]] = relationship(back_populates="order", cascade="all, delete-orphan")
    feedbacks: Mapped[list["OrderFeedback"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    def __init__(
        self,
        *,
        external_id: int | None = None,
        link: str,
        title: str,
        summary: str | None = None,
        pub_date: datetime | None = None,
        rss_raw: dict | None = None,
        enriched_json: dict | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.external_id = external_id
        self.link = link
        self.title = title
        self.summary = summary
        self.pub_date = pub_date
        self.rss_raw = rss_raw or {}
        self.enriched_json = enriched_json or {}
        self.created_at = created_at or datetime.now(UTC)
        self.updated_at = updated_at or datetime.now(UTC)
        self.attachments = []


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    order: Mapped[Order] = relationship(back_populates="attachments")

    def __init__(
        self,
        *,
        order_id: int,
        filename: str,
        stored_path: str,
        size_bytes: int,
        mime_type: str | None = None,
        original_url: str | None = None,
        page_url: str | None = None,
        sha256: str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.order_id = order_id
        self.filename = filename
        self.stored_path = stored_path
        self.size_bytes = size_bytes
        self.mime_type = mime_type
        self.original_url = original_url
        self.page_url = page_url
        self.sha256 = sha256
        self.created_at = created_at or datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    uid: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    competencies_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    categories: Mapped[list[str] | None] = mapped_column(CategoriesType, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now(), nullable=False
    )

    attachments: Mapped[list["UserAttachment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    feedbacks: Mapped[list["OrderFeedback"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserAttachment(Base):
    __tablename__ = "user_attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_uid: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("users.uid", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="attachments")


class OrderFeedback(Base):
    """Модель для откликов на заказы"""
    __tablename__ = "order_feedbacks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("users.uid", ondelete="CASCADE"), nullable=False, index=True
    )
    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # pending, accepted, rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now(), nullable=False
    )

    # Relationships
    order: Mapped["Order"] = relationship(back_populates="feedbacks")
    user: Mapped["User"] = relationship(back_populates="feedbacks")
