from __future__ import annotations

import asyncio
import logging
from typing import List

from fastapi import APIRouter, HTTPException, Response
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.models.schemas import (
    GenerateRequest,
    PlanRequest,
    PlanResponse,
    SlideData,
    SlideReadyEvent,
    SlideErrorEvent,
    DeckCompleteEvent,
    ErrorEvent,
    GenerationStartedEvent,
    ThemeListItem,
    PagePlanItem,
)
from app.store import deck_store
from app.plan_store import plan_store
from app.services.llm import llm_service
from app.services.validator import validate_slide_html
from app.services.slidehtml_normalizer import normalize_slide_html
from app.services.template_loader import template_loader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generate"])

MAX_RETRIES = 2


def _log_input_preview(text: str) -> None:
    n = max(0, settings.log_input_preview_chars)
    if n == 0:
        logger.info("Generate request: length=%d (preview disabled)", len(text))
        return
    preview = text[:n]
    if len(text) > n:
        preview += "..."
    preview = preview.replace("\r\n", " ").replace("\n", " ")
    logger.info(
        "Generate request: length=%d preview=%r",
        len(text),
        preview,
    )


def _validate_and_normalize_pages(
    pages: list[PagePlanItem], theme_id: str
) -> list[PagePlanItem]:
    allowed = set(template_loader.slide_kind_ids(theme_id))
    for p in pages:
        if p.template not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"허용되지 않은 슬라이드 종류: {p.template}",
            )
    ordered = sorted(pages, key=lambda x: x.index)
    out: list[PagePlanItem] = []
    for i, p in enumerate(ordered):
        out.append(p.model_copy(update={"index": i + 1}))
    if not out:
        raise HTTPException(status_code=422, detail="pages가 비어 있습니다.")
    if len(out) > settings.max_slides:
        out = out[: settings.max_slides]
    return out


def _slide_error_event(index: int, error: str, retrying: bool) -> dict:
    return {
        "event": "slide_error",
        "data": SlideErrorEvent(
            index=index,
            error=error,
            retrying=retrying,
        ).model_dump_json(),
    }


def _error_event(code: str, message: str) -> dict:
    return {
        "event": "error",
        "data": ErrorEvent(code=code, message=message).model_dump_json(),
    }


def _format_llm_error(exc: Exception) -> str:
    message = str(exc).strip()
    lowered = message.lower()
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        cause_message = _format_llm_error(cause)
        if cause_message != "LLM 호출 중 오류가 발생했습니다.":
            return cause_message
    if lowered == "llm stream interrupted":
        return "LLM 스트리밍 응답이 중간에 끊겼습니다."
    if "incomplete chunked read" in lowered or "peer closed connection" in lowered:
        return "LLM 스트리밍 응답이 중간에 끊겼습니다."
    if not message:
        return "LLM 호출 중 오류가 발생했습니다."
    return message


async def _prepare_slide_result(
    slide_index: int,
    slide_info: dict,
    expected: PagePlanItem,
    manifests: dict,
    text: str,
    theme_id: str,
) -> tuple[list[dict], SlideData | None]:
    events: list[dict] = []

    template = slide_info["template"]
    preview_html = slide_info["html"]

    if slide_info["id"] != expected.index or template != expected.template:
        events.append(
            _slide_error_event(
                slide_index,
                (
                    f"계획 불일치: 기대 id={expected.index} template={expected.template}, "
                    f"수신 id={slide_info['id']} template={template}"
                ),
                True,
            )
        )
        try:
            fixed = await llm_service.retry_slide(
                slide_id=expected.index,
                template=expected.template,
                errors=[
                    "슬라이드 구분자의 id/template이 확정 계획과 일치해야 합니다.",
                ],
                portfolio_text=text,
                theme_id=theme_id,
                page_plan=expected,
            )
        except Exception as exc:
            logger.exception("계획 불일치 재생성 실패")
            events.append(
                _slide_error_event(
                    slide_index,
                    f"계획에 맞는 슬라이드를 재생성하지 못했습니다: {_format_llm_error(exc)}",
                    False,
                )
            )
            return events, None
        if not fixed:
            events.append(
                _slide_error_event(
                    slide_index,
                    "계획에 맞는 슬라이드를 재생성하지 못했습니다.",
                    False,
                )
            )
            return events, None
        slide_info = {
            "id": expected.index,
            "template": expected.template,
            "html": fixed,
        }
        template = expected.template
        preview_html = fixed

    manifest = manifests.get(template)
    if not manifest:
        events.append(
            _slide_error_event(
                slide_index,
                f"알 수 없는 슬라이드 종류: {template}",
                False,
            )
        )
        return events, None

    valid_html = preview_html
    for attempt in range(MAX_RETRIES + 1):
        normalization_error = None
        try:
            export_html = normalize_slide_html(
                valid_html,
                manifest,
                expected.index,
            )
        except Exception as exc:
            export_html = valid_html
            normalization_error = f"normalize.failed: {exc}"

        result = validate_slide_html(export_html, manifest)
        if normalization_error:
            result.add_error(normalization_error)

        if result.valid:
            return (
                events,
                SlideData(
                    index=slide_index,
                    template=template,
                    html=valid_html,
                    export_html=export_html,
                ),
            )

        if attempt < MAX_RETRIES:
            events.append(
                _slide_error_event(
                    slide_index,
                    "; ".join(result.errors),
                    True,
                )
            )
            try:
                retried = await llm_service.retry_slide(
                    slide_id=slide_info["id"],
                    template=template,
                    errors=result.errors,
                    portfolio_text=text,
                    theme_id=theme_id,
                    page_plan=expected,
                )
            except Exception as exc:
                logger.exception("재시도 LLM 호출 실패")
                events.append(
                    _slide_error_event(
                        slide_index,
                        f"슬라이드를 재생성하지 못했습니다: {_format_llm_error(exc)}",
                        False,
                    )
                )
                return events, None
            if retried:
                valid_html = retried
        else:
            events.append(
                _slide_error_event(
                    slide_index,
                    f"검증 실패 (재시도 {MAX_RETRIES}회 초과): {'; '.join(result.errors)}",
                    False,
                )
            )

    return events, None


async def _generate_stream(
    text: str, theme_id: str, pages: list[PagePlanItem]
):
    """SSE: 확정 플랜 기준 LLM 스트림 → 슬라이드 단위 검증 후 전송."""
    deck = deck_store.create_deck(theme_id)
    manifests = template_loader.all_manifests(theme_id)

    yield {
        "event": "generation_started",
        "data": GenerationStartedEvent(deck_id=deck.deck_id).model_dump_json(),
    }
    await asyncio.sleep(0)

    slide_index = 0
    stream_error: Exception | None = None

    try:
        async for slide_info in llm_service.stream_generate_deck(text, theme_id, pages):
            if slide_index >= len(pages):
                logger.warning("플랜 장수 초과 슬라이드 무시")
                break

            expected = pages[slide_index]
            events, slide_data = await _prepare_slide_result(
                slide_index=slide_index,
                slide_info=slide_info,
                expected=expected,
                manifests=manifests,
                text=text,
                theme_id=theme_id,
            )
            for event in events:
                yield event
                await asyncio.sleep(0)

            if slide_data is not None:
                deck_store.add_slide(deck.deck_id, slide_data)
                yield {
                    "event": "slide_ready",
                    "data": SlideReadyEvent(
                        index=slide_data.index,
                        template=slide_data.template,
                        html=slide_data.html,
                    ).model_dump_json(),
                }
                await asyncio.sleep(0)

            slide_index += 1

    except Exception as e:
        stream_error = e
        logger.warning(
            "LLM 스트림이 중간에 끊겼습니다. 남은 슬라이드를 개별 생성으로 복구합니다: %s",
            _format_llm_error(e),
        )

    if stream_error is not None:
        if slide_index < len(pages):
            yield _slide_error_event(
                slide_index,
                "스트림 연결이 끊겨 남은 슬라이드를 개별 생성으로 복구합니다.",
                True,
            )
            await asyncio.sleep(0)

        while slide_index < len(pages):
            expected = pages[slide_index]
            try:
                recovered_html = await llm_service.generate_slide_from_plan(
                    text,
                    theme_id,
                    expected,
                )
            except Exception as exc:
                logger.exception("개별 슬라이드 생성 실패")
                yield _slide_error_event(
                    slide_index,
                    f"슬라이드 복구 실패: {_format_llm_error(exc)}",
                    False,
                )
                await asyncio.sleep(0)
                slide_index += 1
                continue

            if not recovered_html:
                yield _slide_error_event(
                    slide_index,
                    "슬라이드 HTML을 생성하지 못했습니다.",
                    False,
                )
                await asyncio.sleep(0)
                slide_index += 1
                continue

            events, slide_data = await _prepare_slide_result(
                slide_index=slide_index,
                slide_info={
                    "id": expected.index,
                    "template": expected.template,
                    "html": recovered_html,
                },
                expected=expected,
                manifests=manifests,
                text=text,
                theme_id=theme_id,
            )
            for event in events:
                yield event
                await asyncio.sleep(0)

            if slide_data is not None:
                deck_store.add_slide(deck.deck_id, slide_data)
                yield {
                    "event": "slide_ready",
                    "data": SlideReadyEvent(
                        index=slide_data.index,
                        template=slide_data.template,
                        html=slide_data.html,
                    ).model_dump_json(),
                }
                await asyncio.sleep(0)

            slide_index += 1

    if not deck.slides:
        message = "슬라이드를 생성하지 못했습니다."
        if stream_error is not None:
            message = f"{_format_llm_error(stream_error)} 개별 복구도 완료하지 못했습니다."
        yield _error_event("LLM_ERROR", message)
        return

    yield {
        "event": "deck_complete",
        "data": DeckCompleteEvent(
            deck_id=deck.deck_id,
            total_slides=len(deck.slides),
        ).model_dump_json(),
    }


@router.get("/slide-kinds/{theme_id}")
async def list_slide_kinds(theme_id: str):
    """테마별 선택 가능한 슬라이드 종류 ID(편집 UI용)."""
    if theme_id not in template_loader.theme_ids():
        raise HTTPException(
            status_code=422,
            detail=f"알 수 없는 템플릿(테마): {theme_id}",
        )
    items: list[dict] = []
    for sk in template_loader.slide_kind_ids(theme_id):
        m = template_loader.manifest(theme_id, sk)
        items.append({"id": m.template_id, "name": m.name})
    return items


@router.get("/themes", response_model=List[ThemeListItem])
async def list_themes(response: Response):
    """생성 시 선택 가능한 디자인 템플릿(테마) 목록."""
    response.headers["X-Slide-Templates-Dir"] = str(template_loader._dir)
    items: list[ThemeListItem] = []
    for tid in template_loader.theme_ids():
        tm = template_loader.theme_manifest(tid)
        n = len(template_loader.slide_kind_ids(tid))
        items.append(
            ThemeListItem(
                theme_id=tm.theme_id,
                name=tm.name,
                description=tm.description,
                slide_count=n,
            )
        )
    return items


@router.post("/plan", response_model=PlanResponse)
async def create_plan(body: PlanRequest):
    """1단계: 개요 + 슬라이드 플랜 생성 후 plan_id 발급."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="텍스트를 입력해주세요.")

    theme_id = body.theme_id.strip()
    if theme_id not in template_loader.theme_ids():
        raise HTTPException(
            status_code=422,
            detail=f"알 수 없는 템플릿(테마): {theme_id}",
        )

    _log_input_preview(text)

    try:
        outline, pages = await llm_service.generate_plan(text, theme_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception("플랜 생성 실패")
        raise HTTPException(
            status_code=500, detail=f"플랜 생성에 실패했습니다: {e}"
        ) from e

    rec = plan_store.create_plan(outline, pages, theme_id, text)
    return PlanResponse(
        plan_id=rec.plan_id,
        outline=outline,
        pages=pages,
        theme_id=theme_id,
    )


@router.post("/generate")
async def generate_slides(body: GenerateRequest):
    """2단계: 확정 plan으로 슬라이드 SSE 생성."""
    rec = plan_store.get_plan(body.plan_id)
    if rec is None:
        raise HTTPException(
            status_code=422,
            detail="만료되었거나 알 수 없는 plan_id입니다. 다시 플랜을 생성해 주세요.",
        )

    if body.pages is not None:
        pages = _validate_and_normalize_pages(body.pages, rec.theme_id)
    else:
        pages = rec.pages

    text = rec.source_text
    theme_id = rec.theme_id

    _log_input_preview(text)

    return EventSourceResponse(_generate_stream(text, theme_id, pages))
