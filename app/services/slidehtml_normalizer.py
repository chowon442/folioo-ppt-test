from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Iterable

from lxml import etree, html as lxml_html

from app.models.slidehtml import TemplateManifest, first_export_mode

_TEXT_LIKE_TAGS = {"h1", "h2", "h3", "p", "span", "blockquote", "cite", "strong", "em"}
_NATIVE_UNSAFE_STYLE_HINTS = (
    "background-image",
    "box-shadow",
    "filter",
    "mix-blend-mode",
    "backdrop-filter",
)
EXPORT_MODE_ATTR = "data-sh-export-mode"
STRICT_EXPORT_MODE = "strict"


def _slug(value: str) -> str:
    cleaned = []
    for ch in value.lower():
        if ch.isalnum():
            cleaned.append(ch)
        elif ch in {"_", "-", " "}:
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    return slug or "node"


def _ensure_class(node, class_name: str) -> None:
    existing = node.get("class", "").split()
    if class_name not in existing:
        existing.append(class_name)
    node.set("class", " ".join(x for x in existing if x))


def _replace_list_children(node) -> None:
    for list_node in list(node.xpath("./ul | ./ol")):
        paragraphs = []
        for li in list_node.xpath("./li"):
            p = etree.Element("p")
            p.set("data-sh-level", "0")
            for child in li:
                p.append(deepcopy(child))
            if li.text and li.text.strip():
                p.text = li.text.strip()
            if not len(p) and not (p.text or "").strip():
                p.text = "".join(li.itertext()).strip()
            paragraphs.append(p)
        insert_at = node.index(list_node)
        for offset, p in enumerate(paragraphs):
            node.insert(insert_at + offset, p)
        node.remove(list_node)


def _prune_chart_preview_markup(node) -> None:
    for child in list(node):
        tag = (getattr(child, "tag", "") or "").lower() if hasattr(child, "tag") else ""
        if tag != "script" or child.get("type") != "application/json":
            node.remove(child)


def _iter_exportable(root) -> Iterable:
    return root.xpath(".//*[@data-sh-kind]")


def normalize_slide_html(
    html_str: str,
    manifest: TemplateManifest,
    slide_index: int | None = None,
    *,
    mode: str = "export",
) -> str:
    try:
        root = lxml_html.fragment_fromstring(html_str, create_parent=False)
    except Exception:
        root = lxml_html.fromstring(html_str)

    if root.tag.lower() != "section":
        sections = root.xpath(".//section")
        if not sections:
            raise ValueError("slide root must be a <section>")
        root = sections[0]

    _ensure_class(root, "slide")
    _ensure_class(root, "sh-slide")

    root.set("data-template", manifest.template_id)
    root.set("data-sh-template", manifest.template_id)
    root.set("data-sh-size", f"{manifest.slide.width}x{manifest.slide.height}")
    export_mode = mode == "export"
    if export_mode:
        root.set(EXPORT_MODE_ATTR, STRICT_EXPORT_MODE)
    else:
        root.attrib.pop(EXPORT_MODE_ATTR, None)

    if not export_mode:
        return lxml_html.tostring(root, encoding="unicode", method="html")

    slide_id = root.get("data-sh-id")
    if not slide_id:
        suffix = f"{slide_index:02d}" if slide_index is not None else "01"
        slide_id = f"slide-{suffix}-{_slug(manifest.template_id)}"
        root.set("data-sh-id", slide_id)

    if slide_index is not None and not root.get("data-sh-page-number"):
        root.set("data-sh-page-number", str(slide_index))

    counters: defaultdict[str, int] = defaultdict(int)

    for node in _iter_exportable(root):
        kind = (node.get("data-sh-kind") or "text").strip()
        role = node.get("data-sh-role")
        role_spec = manifest.role_spec(role)

        if role_spec and not node.get("data-sh-fit") and role_spec.fit:
            node.set("data-sh-fit", role_spec.fit)
        if role_spec and not node.get("data-sh-max-lines") and role_spec.max_lines:
            node.set("data-sh-max-lines", str(role_spec.max_lines))
        if role_spec and not node.get("data-sh-min-font") and role_spec.min_font:
            node.set("data-sh-min-font", str(role_spec.min_font))
        if role_spec and not node.get("data-sh-max-font") and role_spec.max_font:
            node.set("data-sh-max-font", str(role_spec.max_font))
        if role_spec and not node.get("data-sh-valign") and role_spec.valign:
            node.set("data-sh-valign", role_spec.valign)
        placeholder_name = None
        if role:
            placeholder_name = manifest.placeholder_map.get(role)
        if role_spec and role_spec.placeholder:
            placeholder_name = role_spec.placeholder
        if placeholder_name and not node.get("data-sh-placeholder"):
            node.set("data-sh-placeholder", placeholder_name)
        if role_spec and role_spec.token_class:
            _ensure_class(node, role_spec.token_class)

        chain = role_spec.export_chain if role_spec else manifest.export_chain_for_kind(kind)
        if not node.get("data-sh-fallback"):
            node.set("data-sh-fallback", chain)
        if not node.get("data-sh-export"):
            node.set("data-sh-export", first_export_mode(chain))

        if kind == "text":
            _replace_list_children(node)
            if not node.get("data-sh-fit"):
                node.set("data-sh-fit", "truncate")
            if not node.get("data-sh-max-lines"):
                node.set("data-sh-max-lines", "6")
        elif kind == "chart":
            _prune_chart_preview_markup(node)

        style = (node.get("style") or "").lower()
        if kind not in {"flatten", "svg"} and any(token in style for token in _NATIVE_UNSAFE_STYLE_HINTS):
            node.set("data-sh-export", "png")
            node.set("data-sh-fallback", "png")

        if not node.get("data-sh-id"):
            basis = role or kind
            counters[basis] += 1
            suffix = counters[basis]
            if suffix == 1:
                node_id = f"{slide_id}__{_slug(basis)}"
            else:
                node_id = f"{slide_id}__{_slug(basis)}-{suffix}"
            node.set("data-sh-id", node_id)

    for node in root.xpath(".//*[not(@data-sh-kind)][self::h1 or self::h2 or self::h3 or self::p or self::span or self::blockquote or self::cite]"):
        role = node.get("data-sh-role")
        if role and role in manifest.roles:
            node.set("data-sh-kind", "text")
            _replace_list_children(node)

    return lxml_html.tostring(root, encoding="unicode", method="html")
