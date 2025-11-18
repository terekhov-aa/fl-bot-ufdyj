from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RSSIngestRequest(BaseModel):
    feed_url: Optional[str] = None
    category: Optional[int] = None
    subcategory: Optional[int] = None
    limit: Optional[int] = None


class RSSIngestResponse(BaseModel):
    status: str
    inserted: int
    updated: int


class AttachmentResponse(BaseModel):
    id: int
    filename: str
    size_bytes: int
    mime_type: Optional[str] = None
    original_url: Optional[str] = None
    page_url: Optional[str] = None
    sha256: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    external_id: Optional[int]
    link: str
    title: str
    summary: Optional[str] = None
    pub_date: Optional[datetime] = None
    rss_raw: dict[str, Any]
    enriched: dict[str, Any]
    attachments: list[AttachmentResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrdersListResponse(BaseModel):
    items: list[OrderResponse]
    limit: int
    offset: int


class UploadMetadataResponse(BaseModel):
    status: str
    mode: str
    order: dict[str, Any]


class UploadAttachmentResponse(BaseModel):
    status: str
    mode: str
    file: dict[str, Any]
    order: dict[str, Any]


class UserCreateResponse(BaseModel):
    uid: UUID


class UserAttachmentOut(BaseModel):
    id: int
    filename: str
    stored_path: str
    size: int
    sha256: str
    content_type: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPatch(BaseModel):
    competencies_text: Optional[str] = None
    categories: Optional[list[str]] = None


class UserDetail(BaseModel):
    uid: UUID
    competencies_text: Optional[str] = None
    categories: Optional[list[str]] = None
    attachments: list[UserAttachmentOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrderFeedbackCreate(BaseModel):
    """Схема для создания отклика на заказ"""
    order_id: int
    user_id: UUID
    feedback_text: str


class OrderFeedbackResponse(BaseModel):
    """Схема для ответа отклика на заказ"""
    id: int
    order_id: int
    user_id: UUID
    feedback_text: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderFeedbackListResponse(BaseModel):
    """Схема для списка откликов"""
    items: list[OrderFeedbackResponse]
    limit: int
    offset: int


class ParseSiteRequest(BaseModel):
    url: str
    instruction: Optional[str] = None
    schema_: Optional[dict[str, Any]] = Field(default=None, alias="schema")
    options: Optional[dict[str, Any]] = None

    model_config = ConfigDict(populate_by_name=True)


class ParseSiteResponse(BaseModel):
    result: dict[str, Any]
