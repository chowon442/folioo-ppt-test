from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.config import settings
from app.models.slidehtml import TemplateManifest, ThemeManifest


class SlideData(BaseModel):
    index: int
    template: str
    html: str
    export_html: str | None = Field(default=None, exclude=True)


class DeckData(BaseModel):
    deck_id: str
    slides: list[SlideData] = Field(default_factory=list)
    created_at: float
    theme_id: str = "default"


class PagePlanItem(BaseModel):
    """1단계에서 확정되는 슬라이드 단위 계획."""

    index: int = Field(..., ge=1, description="슬라이드 번호 (1부터, SLIDE id와 일치)")
    template: str = Field(..., min_length=1, max_length=64, description="슬라이드 종류 ID")
    title: str = Field(default="", max_length=200)
    purpose: str = Field(default="", max_length=500)
    key_points: list[str] = Field(default_factory=list, max_length=12)


class GenerationPlanRecord(BaseModel):
    """서버에 저장되는 생성 계획(원문 포함)."""

    plan_id: str
    outline: str
    pages: list[PagePlanItem]
    theme_id: str
    source_text: str
    created_at: float


class PlanRequest(BaseModel):
    text: str = Field(..., max_length=settings.max_input_length)
    theme_id: str = Field(default="default", min_length=1, max_length=64)


class PlanResponse(BaseModel):
    plan_id: str
    outline: str
    pages: list[PagePlanItem]
    theme_id: str


class GenerateRequest(BaseModel):
    """2단계: 확정된 plan_id로 생성. pages가 있으면 저장된 계획을 대체(사용자 편집)."""

    plan_id: str = Field(..., min_length=1, max_length=64)
    pages: list[PagePlanItem] | None = None


class ExportRequest(BaseModel):
    pass


class SSEEventType(str, Enum):
    SLIDE_READY = "slide_ready"
    SLIDE_ERROR = "slide_error"
    DECK_COMPLETE = "deck_complete"
    ERROR = "error"


class SlideReadyEvent(BaseModel):
    index: int
    template: str
    html: str


class SlideErrorEvent(BaseModel):
    index: int
    error: str
    retrying: bool


class GenerationStartedEvent(BaseModel):
    deck_id: str


class DeckCompleteEvent(BaseModel):
    deck_id: str
    total_slides: int


class ErrorEvent(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorEvent


class ThemeListItem(BaseModel):
    theme_id: str
    name: str
    description: str
    slide_count: int
