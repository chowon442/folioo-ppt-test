from __future__ import annotations

import asyncio
import json
import re
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel

from app.config import settings
from app.models.schemas import PagePlanItem
from app.services.template_loader import template_loader
from app.services.html_sanitizer import (
    consume_complete_slides,
    parse_slides,
    strip_codefences,
)

if TYPE_CHECKING:
    from openai import AsyncOpenAI
else:
    AsyncOpenAI = Any


def _slide_kinds_catalog(theme_id: str) -> str:
    lines: list[str] = []
    for sk in template_loader.slide_kind_ids(theme_id):
        m = template_loader.manifest(theme_id, sk)
        lines.append(f"- `{m.template_id}` ({m.name}): {m.description}")
    return "\n".join(lines) if lines else "(없음)"


def _build_plan_system_prompt(theme_id: str) -> str:
    tm = template_loader.theme_manifest(theme_id)
    catalog = _slide_kinds_catalog(theme_id)
    return f"""당신은 프레젠테이션 구조 설계자입니다. 사용자 포트폴리오를 읽고 **슬라이드 계획만** JSON으로 제안합니다. HTML은 출력하지 마세요.

## 테마
- 이름: {tm.name}
- theme_id: `{theme_id}`

## 사용 가능한 슬라이드 종류 (반드시 아래 template_id 중에서만 선택)
{catalog}

## 규칙
1. 출력은 **유효한 JSON 한 덩어리**뿐입니다. 마크다운/코드펜스/설명 문장을 덧붙이지 마세요.
2. JSON 스키마:
{{
  "outline": "전체 스토리라인 요약 (3~8문장)",
  "pages": [
    {{
      "index": 1,
      "template": "슬라이드종류ID",
      "title": "이 슬라이드 제목",
      "purpose": "이 슬라이드가 담당할 설명 (한 문장)",
      "key_points": ["불릿1", "불릿2"]
    }}
  ]
}}
3. `index`는 1부터 순차 증가. 첫 슬라이드는 보통 cover, 마지막은 closing을 권장합니다.
4. 페이지 수는 1~{settings.max_slides}장.
5. 포트폴리오에 수치가 있으면 metrics_table 또는 bar_chart를 계획에 포함하는 것을 권장합니다.
"""


def _build_system_prompt(theme_id: str) -> str:
    tm = template_loader.theme_manifest(theme_id)
    ref = template_loader.build_prompt_reference(theme_id)
    return SYSTEM_PROMPT_TEMPLATE.format(
        max_slides=settings.max_slides,
        template_reference=ref,
        theme_name=tm.name,
        theme_id=theme_id,
    )


SYSTEM_PROMPT_TEMPLATE = """당신은 SlideHTML DSL v1 슬라이드 생성 전문가입니다. 사용자의 포트폴리오 텍스트를 분석하여 프레젠테이션 슬라이드 HTML을 생성합니다.

## 선택된 디자인 템플릿(테마)

- **이름**: {theme_name}
- **theme_id**: `{theme_id}`

사용자가 고른 시각 스타일·레이아웃 세트입니다. 아래 **슬라이드 종류**(cover, skills 등)만 사용하세요. 구분자 `template="..."`, `data-template="..."`, `data-sh-template="..."`에는 **슬라이드 종류 ID**만 넣습니다.

## 출력 규칙

1. 마크다운 코드블록(```)을 절대 사용하지 마세요. 첫 문자부터 슬라이드 구분자로 시작하세요.
2. 슬라이드는 id 순서대로 **앞에서부터 연속 출력**하세요 (스트리밍 중 첫 슬라이드부터 완성되도록).
3. 각 슬라이드 앞에 반드시 구분자를 넣으세요:
   <!-- SLIDE id="1" template="cover" -->
4. 슬라이드 HTML은 반드시 SlideHTML DSL v1 규약을 따르세요.

## 구조 규약

- 각 슬라이드 root는 반드시 `<section class="slide sh-slide" ...>` 이어야 합니다.
- root에는 `data-template`, `data-sh-template`, `data-sh-size="1280x720"` 를 넣으세요.
- exportable node는 반드시 `data-sh-kind` 를 가져야 합니다.
- 텍스트 node는 반드시 `data-sh-role`, `data-sh-fit`, `data-sh-max-lines` 를 가져야 합니다.
- 차트 node는 반드시 `data-sh-chart-kind` 와 `script[type="application/json"]` 를 가져야 합니다.
- 표 node는 반드시 실제 `<table data-sh-kind="table">` 이어야 합니다.
- CSS 클래스 이름과 DOM 골격은 각 슬라이드 종류의 참조 HTML과 동일하게 유지하세요.
- `data-sh-id` 는 참조 HTML이 있으면 유지하세요. 서버가 최종적으로 다시 정규화합니다.

## 허용/금지 사항

- 허용 태그: section, div, aside, h1~h3, p, span, a, br, strong, em, u, mark, blockquote, cite, img, table, thead, tbody, tr, th, td, svg, g, path, rect, circle, ellipse, line, polyline, polygon, defs, linearGradient, radialGradient, stop, use, script[type="application/json"]
- 금지 태그: style, link, iframe, object, embed, form, input, canvas, video
- 임의 class를 만들지 마세요.
- 임의 DOM 구조를 만들지 말고, 반드시 참조 HTML 골격 안에서만 내용을 채우세요.
- 핵심 콘텐츠를 pseudo-element, background-image, box-shadow, filter, CSS content 에 넣지 마세요.
- 레이아웃 helper는 `data-sh-kind="layout"` 에만 두세요.
- 핵심 콘텐츠는 반드시 exportable leaf node로 표현하세요.
- bullet이 필요하면 `<p data-sh-level="0">...</p>` 형태를 사용하세요. 자유 `<ul>/<li>` 의미에 의존하지 마세요.

## 슬라이드 구성 가이드

- 첫 번째 슬라이드는 반드시 cover 템플릿을 사용하세요.
- 기술 역량이 있으면 skills 템플릿으로 정리하세요.
- 경력/이력이 있으면 timeline 템플릿을 사용하세요.
- 프로젝트별로 project_card 1장을 사용하세요.
- 개요나 비교 설명에는 two_column을 사용하세요.
- 마지막 슬라이드는 closing 템플릿으로 마무리하세요.
- 최대 {max_slides}장까지 생성 가능합니다.

### 표·그래프 (수치·비율이 있으면 반드시 활용)

- **metrics_table**: 반드시 explicit `<table data-sh-kind="table">` 로 표현하세요. 셀 안에는 텍스트 계열 태그만 사용하세요.
- **bar_chart**: 렌더된 SVG 막대를 직접 만들지 말고, 반드시 `data-sh-kind="chart"` node와 `script[type="application/json"]` 데이터만 넣으세요.
- 포트폴리오에 **구체적 숫자·퍼센트·기간·규모**가 있으면 **metrics_table 또는 bar_chart 중 최소 1장**을 포함하는 것을 강력히 권장합니다. 숫자가 적어도 요약 가능한 항목(예: 기술 비중, 프로젝트 기여도)이 있으면 표나 막대로 가공해 넣으세요.

- 추천 순서: cover → skills/timeline → project_card(들) → **metrics_table / bar_chart** (해당 시) → two_column(선택) → closing

## 이 테마에서 사용 가능한 슬라이드 종류

{template_reference}
"""


RETRY_PROMPT_TEMPLATE = """이전에 생성한 슬라이드 #{slide_id} (template: {template})에 오류가 있습니다.

오류 내용:
{errors}

위 오류를 수정하여 해당 슬라이드의 **SlideHTML DSL v1 HTML만** 다시 생성해주세요.
구분자 없이, `<section class="slide sh-slide" ...>` 태그부터 시작하세요.
"""


class _PlanJsonModel(BaseModel):
    outline: str
    pages: list[PagePlanItem]


class LLMStreamInterruptedError(RuntimeError):
    """업스트림 스트림 연결이 중간에 끊긴 경우."""


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    text = strip_codefences(text)
    m = re.search(r"\{[\s\S]*\}\s*$", text)
    if m:
        text = m.group(0)
    return json.loads(text)


def _extract_first_slide_html(raw: str) -> str | None:
    text = strip_codefences(raw or "")
    if not text:
        return None
    slides = parse_slides(text)
    if slides:
        return slides[0]["html"]
    return text.strip() if "<section" in text else None


class LLMService:
    def __init__(self):
        self._client: AsyncOpenAI | None = None
        self._system_prompt_cache: dict[str, str] = {}

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            try:
                from openai import AsyncOpenAI as _AsyncOpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "openai 패키지가 설치되어 있지 않아 LLM 생성을 실행할 수 없습니다."
                ) from exc
            self._client = _AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key,
            )
        return self._client

    def system_prompt_for_theme(self, theme_id: str) -> str:
        if theme_id not in self._system_prompt_cache:
            self._system_prompt_cache[theme_id] = _build_system_prompt(theme_id)
        return self._system_prompt_cache[theme_id]

    async def generate_plan(
        self, portfolio_text: str, theme_id: str
    ) -> tuple[str, list[PagePlanItem]]:
        """1단계: 개요 + 페이지 플랜(JSON)."""
        response = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _build_plan_system_prompt(theme_id)},
                {
                    "role": "user",
                    "content": f"다음 포트폴리오를 분석해 슬라이드 계획 JSON을 작성하세요.\n\n{portfolio_text}",
                },
            ],
        )
        raw = response.choices[0].message.content or ""
        data = _extract_json_object(raw)
        parsed = _PlanJsonModel.model_validate(data)
        allowed = set(template_loader.slide_kind_ids(theme_id))
        pages: list[PagePlanItem] = []
        for i, p in enumerate(sorted(parsed.pages, key=lambda x: x.index)):
            tid = p.template.strip()
            if tid not in allowed:
                raise ValueError(f"허용되지 않은 슬라이드 종류: {tid}")
            pages.append(
                PagePlanItem(
                    index=i + 1,
                    template=tid,
                    title=p.title,
                    purpose=p.purpose,
                    key_points=p.key_points[:12],
                )
            )
        if not pages:
            raise ValueError("pages가 비어 있습니다.")
        if len(pages) > settings.max_slides:
            pages = pages[: settings.max_slides]
        outline = parsed.outline.strip()
        return outline, pages

    def _build_step2_user_message(
        self, portfolio_text: str, pages: list[PagePlanItem]
    ) -> str:
        lines = [
            "아래 **확정된 슬라이드 계획**을 정확히 따르세요. 슬라이드 개수·순서·template id는 계획과 동일해야 합니다.",
            "",
            "## 포트폴리오 원문",
            portfolio_text,
            "",
            "## 확정 계획 (슬라이드별)",
        ]
        for p in pages:
            kp = "\n".join(f"  - {k}" for k in p.key_points) if p.key_points else "  (없음)"
            lines.append(
                f"- SLIDE id={p.index} template=`{p.template}`\n"
                f"  제목: {p.title}\n"
                f"  목적: {p.purpose}\n"
                f"  핵심:\n{kp}"
            )
        lines.append("")
        lines.append(
            f"위 계획대로 정확히 {len(pages)}장을 생성하세요. "
            "각 슬라이드 구분자의 id와 template은 계획과 일치해야 합니다."
        )
        return "\n".join(lines)

    def _build_single_slide_user_message(
        self, portfolio_text: str, page: PagePlanItem
    ) -> str:
        key_points = (
            "\n".join(f"- {point}" for point in page.key_points)
            if page.key_points
            else "- (없음)"
        )
        return "\n".join(
            [
                "아래 계획의 슬라이드 1장만 생성하세요.",
                "다른 슬라이드나 설명 문장은 절대 출력하지 마세요.",
                "응답은 `<section class=\"slide sh-slide\" ...>` 로 시작하는 HTML만 반환하세요.",
                "",
                "## 포트폴리오 원문",
                portfolio_text,
                "",
                "## 생성할 슬라이드 계획",
                f"- id: {page.index}",
                f"- template: {page.template}",
                f"- 제목: {page.title}",
                f"- 목적: {page.purpose}",
                "- 핵심 포인트:",
                key_points,
            ]
        )

    @staticmethod
    def _take_new_slides(
        slides: list[dict[str, Any]],
        emitted_ids: set[int],
        max_n: int,
        emitted_count: int,
    ) -> tuple[list[dict[str, Any]], int]:
        fresh: list[dict[str, Any]] = []
        for slide in slides:
            if slide["id"] in emitted_ids:
                continue
            if emitted_count >= max_n:
                break
            emitted_ids.add(slide["id"])
            emitted_count += 1
            fresh.append(slide)
        return fresh, emitted_count

    def _collect_tail_slides(
        self,
        buffer: str,
        emitted_ids: set[int],
        max_n: int,
        emitted_count: int,
        *,
        allow_partial_tail: bool,
    ) -> tuple[list[dict[str, Any]], int]:
        produced: list[dict[str, Any]] = []
        tail = strip_codefences(buffer.strip())
        if not tail:
            return produced, emitted_count

        complete_slides, rest = consume_complete_slides(tail)
        fresh, emitted_count = self._take_new_slides(
            complete_slides, emitted_ids, max_n, emitted_count
        )
        produced.extend(fresh)

        rest = strip_codefences(rest.strip()) if rest else ""
        if allow_partial_tail and rest:
            fresh, emitted_count = self._take_new_slides(
                parse_slides(rest), emitted_ids, max_n, emitted_count
            )
            produced.extend(fresh)
        return produced, emitted_count

    async def stream_generate_deck(
        self,
        portfolio_text: str,
        theme_id: str,
        pages: list[PagePlanItem],
    ):
        """2단계: 확정 플랜 기반 토큰 스트림 → 완성 슬라이드 단위 yield."""
        user_content = self._build_step2_user_message(portfolio_text, pages)
        stream = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": self.system_prompt_for_theme(theme_id)},
                {"role": "user", "content": user_content},
            ],
            stream=True,
        )
        buffer = ""
        emitted_ids: set[int] = set()
        max_n = len(pages)
        emitted_count = 0

        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                piece = getattr(delta, "content", None) or ""
                if not piece:
                    continue
                buffer += piece
                new_slides, buffer = consume_complete_slides(buffer)
                fresh, emitted_count = self._take_new_slides(
                    new_slides, emitted_ids, max_n, emitted_count
                )
                for slide in fresh:
                    yield slide
                    # ASGI가 SSE 청크를 클라이언트로 넘길 수 있도록 이벤트 루프에 제어권 반환
                    await asyncio.sleep(0)
                if emitted_count >= max_n:
                    return
        except Exception as exc:
            recovered_slides, emitted_count = self._collect_tail_slides(
                buffer,
                emitted_ids,
                max_n,
                emitted_count,
                allow_partial_tail=False,
            )
            for slide in recovered_slides:
                yield slide
                await asyncio.sleep(0)
            raise LLMStreamInterruptedError("LLM stream interrupted") from exc

        tail_slides, emitted_count = self._collect_tail_slides(
            buffer,
            emitted_ids,
            max_n,
            emitted_count,
            allow_partial_tail=True,
        )
        for slide in tail_slides:
            yield slide
            await asyncio.sleep(0)

    async def generate_slide_from_plan(
        self,
        portfolio_text: str,
        theme_id: str,
        page_plan: PagePlanItem,
    ) -> str | None:
        response = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": self.system_prompt_for_theme(theme_id)},
                {
                    "role": "user",
                    "content": self._build_single_slide_user_message(
                        portfolio_text, page_plan
                    ),
                },
            ],
        )
        return _extract_first_slide_html(response.choices[0].message.content or "")

    async def retry_slide(
        self,
        slide_id: int,
        template: str,
        errors: list[str],
        portfolio_text: str,
        theme_id: str = "default",
        page_plan: PagePlanItem | None = None,
    ) -> str | None:
        extra = ""
        if page_plan is not None:
            extra = (
                f"\n\n이 슬라이드의 계획:\n"
                f"- 제목: {page_plan.title}\n"
                f"- 목적: {page_plan.purpose}\n"
                f"- 핵심: {', '.join(page_plan.key_points) if page_plan.key_points else '(없음)'}\n"
            )
        prompt = RETRY_PROMPT_TEMPLATE.format(
            slide_id=slide_id,
            template=template,
            errors="\n".join(f"- {e}" for e in errors),
        )
        response = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": self.system_prompt_for_theme(theme_id)},
                {
                    "role": "user",
                    "content": f"원본 포트폴리오:\n{portfolio_text}{extra}\n\n{prompt}",
                },
            ],
        )
        return _extract_first_slide_html(response.choices[0].message.content or "")


llm_service = LLMService()
