from __future__ import annotations

import re

CODEFENCE_PATTERN = re.compile(r"^```[a-zA-Z]*\s*\n?", re.MULTILINE)
CODEFENCE_END = re.compile(r"\n?```\s*$", re.MULTILINE)

SLIDE_DELIMITER = re.compile(
    r'<!--\s*SLIDE\s+id="(\d+)"\s+template="([\w-]+)"\s*-->'
)

_SECTION_OPEN = re.compile(r"<section\b", re.IGNORECASE)
_SECTION_CLOSE = re.compile(r"</section>", re.IGNORECASE)
_SLIDE_CLASS = re.compile(r'class="[^"]*\bslide\b[^"]*"', re.IGNORECASE)
_SH_SLIDE_CLASS = re.compile(r'class="[^"]*\bsh-slide\b[^"]*"', re.IGNORECASE)


def _is_complete_slide_html(html: str) -> bool:
    """루트 <section class=\"slide sh-slide\"> 한 블록이 닫혔는지 여부."""
    h = html.strip()
    if not h.startswith("<section"):
        return False
    if not h.rstrip().endswith("</section>"):
        return False
    opens = len(_SECTION_OPEN.findall(h))
    closes = len(_SECTION_CLOSE.findall(h))
    return opens == closes and opens >= 1


def consume_complete_slides(buffer: str) -> tuple[list[dict], str]:
    """스트리밍 버퍼에서 SLIDE 마커 기준 완성된 슬라이드만 꺼내고, 미완성 꼬리는 remainder로 반환."""
    slides: list[dict] = []
    idx = 0
    text = buffer
    while idx < len(text):
        m = SLIDE_DELIMITER.search(text, idx)
        if not m:
            return slides, text[idx:]
        marker_start = m.start()
        slide_id = int(m.group(1))
        template = m.group(2)
        content_start = m.end()
        m_next = SLIDE_DELIMITER.search(text, content_start)
        if m_next:
            chunk_html = text[content_start : m_next.start()].strip()
            if _is_complete_slide_html(chunk_html):
                slides.append(
                    {"id": slide_id, "template": template, "html": chunk_html}
                )
                idx = m_next.start()
                continue
            return slides, text[marker_start:]
        chunk_html = text[content_start:].strip()
        if _is_complete_slide_html(chunk_html):
            slides.append({"id": slide_id, "template": template, "html": chunk_html})
            return slides, ""
        return slides, text[marker_start:]
    return slides, ""


def strip_codefences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = CODEFENCE_PATTERN.sub("", text, count=1)
    if text.rstrip().endswith("```"):
        text = CODEFENCE_END.sub("", text, count=1)
    return text.strip()


def parse_slides(raw_text: str) -> list[dict]:
    """LLM 응답 텍스트를 슬라이드별로 분리한다.

    Returns:
        list of {"id": int, "template": str, "html": str}
    """
    text = strip_codefences(raw_text)

    markers = list(SLIDE_DELIMITER.finditer(text))

    if not markers:
        section_match = re.search(r"<section\b[^>]*>", text, re.IGNORECASE)
        if section_match:
            opening_tag = section_match.group(0)
            if not (_SLIDE_CLASS.search(opening_tag) or _SH_SLIDE_CLASS.search(opening_tag)):
                return []
            template_match = re.search(
                r'data-template="([\w-]+)"', text
            )
            tmpl = template_match.group(1) if template_match else "unknown"
            return [{"id": 1, "template": tmpl, "html": text.strip()}]
        return []

    slides = []
    for i, marker in enumerate(markers):
        slide_id = int(marker.group(1))
        template = marker.group(2)
        start = marker.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        html = text[start:end].strip()
        slides.append({"id": slide_id, "template": template, "html": html})

    return slides
