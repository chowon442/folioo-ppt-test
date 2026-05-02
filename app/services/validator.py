from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

from app.services.slidehtml_validator import (
    SlideHTMLValidator,
    is_slidehtml_document,
    validate_export_html as _validate_export_html,
)

ALLOWED_LEGACY_TAGS = {
    "section",
    "div",
    "span",
    "h1",
    "h2",
    "h3",
    "p",
    "br",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "table",
    "thead",
    "tbody",
    "caption",
    "tr",
    "td",
    "th",
    "img",
    "svg",
    "g",
    "defs",
    "lineargradient",
    "stop",
    "rect",
    "line",
    "text",
    "tspan",
    "path",
    "circle",
    "polyline",
    "polygon",
    "title",
}

FORBIDDEN_LEGACY_TAGS = {
    "script",
    "style",
    "link",
    "iframe",
    "object",
    "embed",
    "form",
    "input",
    "a",
}

ALLOWED_INLINE_STYLES = {
    "font-size",
    "line-height",
    "padding",
    "margin",
    "font-weight",
    "color",
    "text-align",
    "letter-spacing",
}

STYLE_PROP_RE = re.compile(r"([\w-]+)\s*:")


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.valid = False
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def _parse_html(html_str: str):
    try:
        return ET.fromstring(html_str)
    except ET.ParseError:
        return ET.fromstring(f"<fragment>{html_str}</fragment>")


def _class_list(node) -> set[str]:
    return {part for part in (node.get("class", "") or "").split() if part}


def _manifest_value(manifest: Any, key: str, default: Any = None) -> Any:
    if isinstance(manifest, dict):
        return manifest.get(key, default)
    return getattr(manifest, key, default)


def _format_issue(issue) -> str:
    text = f"{issue.code}: {issue.message}"
    if issue.node_id:
        text += f" (node={issue.node_id})"
    if issue.path:
        text += f" (path={issue.path})"
    return text


def _validate_legacy_slide_html(
    html_str: str,
    manifest: Any,
) -> ValidationResult:
    result = ValidationResult()

    try:
        root = _parse_html(html_str)
    except Exception as exc:
        result.add_error(f"HTML parse failed: {exc}")
        return result

    slide_roots = []
    if isinstance(root.tag, str) and root.tag.lower() == "section":
        slide_roots = [root]
    else:
        slide_roots = [
            node
            for node in root.iter()
            if isinstance(node.tag, str)
            and node.tag.lower() == "section"
            and "slide" in _class_list(node)
        ]

    if not slide_roots:
        result.add_error('루트에 <section class="slide" data-template="...">가 없습니다.')
        return result

    slide_root = slide_roots[0]
    tmpl_attr = slide_root.get("data-template", "")
    template_id = _manifest_value(manifest, "template_id")
    if tmpl_attr != template_id:
        result.add_error(
            f'data-template="{tmpl_attr}" 이 manifest의 "{template_id}"와 불일치'
        )

    for el in slide_root.iter():
        if not isinstance(el.tag, str):
            continue
        tag = el.tag.lower()
        if tag in FORBIDDEN_LEGACY_TAGS:
            result.add_error(f"금지 태그 사용: <{tag}>")
        elif tag not in ALLOWED_LEGACY_TAGS:
            result.add_warning(f"비표준 태그 사용: <{tag}>")

        style = el.get("style")
        if style:
            props = STYLE_PROP_RE.findall(style)
            for prop in props:
                if prop.lower() not in ALLOWED_INLINE_STYLES:
                    result.add_error(f"금지된 inline style 속성: {prop}")

    found_slots: dict[str, object] = {}
    for el in slide_root.iter():
        slot_name = el.get("data-slot")
        if not slot_name:
            continue

        if slot_name in found_slots:
            result.add_error(f"슬롯 '{slot_name}' 가 중복 정의됨")
            continue

        found_slots[slot_name] = el

        if not el.get("data-export"):
            result.add_error(f"슬롯 '{slot_name}'에 data-export 속성이 없음")

    for slot_name, spec in _manifest_value(manifest, "slots", {}).items():
        if spec.required and slot_name not in found_slots:
            result.add_error(f"필수 슬롯 '{slot_name}' 누락")

    return result


def validate_slide_html(html_str: str, manifest: Any) -> ValidationResult:
    if is_slidehtml_document(html_str):
        report = SlideHTMLValidator(manifest).validate_html(html_str)
        result = ValidationResult(valid=report.valid)
        for issue in report.errors:
            result.add_error(_format_issue(issue))
        for issue in report.warnings:
            result.add_warning(_format_issue(issue))
        return result

    return _validate_legacy_slide_html(html_str, manifest)


def validate_export_slide_html(html_str: str, manifest: Any) -> ValidationResult:
    report = _validate_export_html(html_str, manifest)
    result = ValidationResult(valid=report.valid)
    for issue in report.errors:
        result.add_error(_format_issue(issue))
    for issue in report.warnings:
        result.add_warning(_format_issue(issue))
    return result
