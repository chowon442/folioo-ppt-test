from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Mapping

DSL_VERSION = "slidehtml/v1"
STRICT_EXPORT_MODE = "strict"
EXPORT_MODE_ATTR = "data-sh-export-mode"

KNOWN_KINDS = frozenset(
    {
        "layout",
        "group",
        "text",
        "shape",
        "image",
        "svg",
        "chart",
        "table",
        "line",
        "flatten",
        "notes",
    }
)

EXPORTABLE_KINDS = frozenset(
    {"group", "text", "shape", "image", "svg", "chart", "table", "line", "flatten"}
)

ALLOWED_EXPORT_MODES = frozenset(
    {"auto", "native", "placeholder", "svg", "png", "ignore", "flatten"}
)

FIT_MODES = frozenset({"none", "shrink", "truncate", "clip", "split"})
STRICT_EXPORT_FIT_MODES = frozenset({"none", "shrink", "truncate"})

STRUCTURAL_CLASSES = frozenset({"sh-deck", "sh-slide", "sh-node"})

TEXT_ALLOWED_TAGS = frozenset({"div", "p", "span", "a", "br", "strong", "em", "u", "mark"})
TABLE_ALLOWED_CELL_TAGS = frozenset({"span", "strong", "em", "u", "mark", "a", "br"})

ALLOWED_TAGS = frozenset(
    {
        "article",
        "section",
        "div",
        "aside",
        "p",
        "span",
        "a",
        "br",
        "strong",
        "em",
        "u",
        "mark",
        "img",
        "svg",
        "g",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "defs",
        "lineargradient",
        "radialgradient",
        "stop",
        "use",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "caption",
        "script",
        "title",
        "tspan",
    }
)

DEFAULT_SLIDE_SIZE = {"width": 1280, "height": 720, "grid": 4}
SUPPORTED_PLACEHOLDER_KINDS = frozenset({"text", "image", "chart", "table"})
STYLE_PROP_RE = re.compile(r"([\w-]+)\s*:")
XML_NAMESPACE_RE = re.compile(r"^\{[^}]+\}")


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    node_id: str | None = None
    path: str | None = None


@dataclass
class ValidationReport:
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(by_alias=True)
        if isinstance(dumped, Mapping):
            return dict(dumped)
        return {}
    if hasattr(value, "dict"):
        dumped = value.dict(by_alias=True)
        if isinstance(dumped, Mapping):
            return dict(dumped)
        return {}
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _normalize_manifest_dict(raw: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw)

    if "templateId" not in data and "template_id" in data:
        data["templateId"] = data["template_id"]

    if "slide" not in data and "slide_size" in data:
        size = list(data.get("slide_size") or [])
        width = int(size[0]) if len(size) > 0 else DEFAULT_SLIDE_SIZE["width"]
        height = int(size[1]) if len(size) > 1 else DEFAULT_SLIDE_SIZE["height"]
        data["slide"] = {"width": width, "height": height, "grid": DEFAULT_SLIDE_SIZE["grid"]}

    alias_pairs = {
        "allowedKinds": "allowed_kinds",
        "allowedRoles": "allowed_roles",
        "allowedClasses": "allowed_classes",
        "defaultExport": "default_export",
        "chartTemplates": "chart_templates",
    }
    for alias, legacy in alias_pairs.items():
        if alias not in data and legacy in data:
            data[alias] = data[legacy]

    if "roles" not in data and isinstance(data.get("slots"), Mapping):
        converted_roles: dict[str, dict[str, Any]] = {}
        for role_name, slot_spec in dict(data["slots"]).items():
            if not isinstance(slot_spec, Mapping):
                continue
            slot_type = str(slot_spec.get("type") or "text").lower()
            kind = {
                "text": "text",
                "richtext": "text",
                "list": "group",
                "image": "image",
                "chart": "chart",
                "table": "table",
            }.get(slot_type, "text")
            export_mode = str(slot_spec.get("export_mode") or "").lower()
            export_chain = {
                "native": "native",
                "svg": "svg",
                "png": "png",
                "placeholder": "placeholder",
                "ignore": "ignore",
                "flatten": "svg",
            }.get(export_mode, None)
            converted_roles[role_name] = {
                "kind": kind,
                "required": bool(slot_spec.get("required", False)),
                "fit": "truncate" if kind == "text" else None,
                "maxLines": slot_spec.get("max_lines"),
                "maxLength": slot_spec.get("max_length"),
                "maxItems": slot_spec.get("max_items"),
                "allowedChildTags": slot_spec.get("allowed_child_tags"),
                "export": export_chain,
            }
        data["roles"] = converted_roles

    if "allowedRoles" not in data and isinstance(data.get("roles"), Mapping):
        data["allowedRoles"] = list(dict(data["roles"]).keys())

    for role_container_name in ("roles", "roleConstraints"):
        role_container = data.get(role_container_name)
        if not isinstance(role_container, Mapping):
            continue
        upgraded_roles: dict[str, Any] = {}
        for role_name, role_spec in dict(role_container).items():
            if not isinstance(role_spec, Mapping):
                upgraded_roles[role_name] = role_spec
                continue
            spec = dict(role_spec)
            if "minFont" not in spec and "minFontPx" in spec:
                spec["minFont"] = spec["minFontPx"]
            if "maxFont" not in spec and "maxFontPx" in spec:
                spec["maxFont"] = spec["maxFontPx"]
            upgraded_roles[role_name] = spec
        data[role_container_name] = upgraded_roles

    if "allowedKinds" not in data and isinstance(data.get("roles"), Mapping):
        role_kinds = {
            spec.get("kind", "text")
            for spec in dict(data["roles"]).values()
            if isinstance(spec, Mapping)
        }
        data["allowedKinds"] = sorted(role_kinds | set(KNOWN_KINDS))

    if "defaultExport" not in data:
        data["defaultExport"] = {
            "layout": "ignore",
            "group": "native>png",
            "text": "native>png",
            "shape": "native>svg>png",
            "image": "native>png",
            "chart": "native>svg>png",
            "table": "native>png",
            "line": "native>png",
            "svg": "svg>png",
            "flatten": "svg>png",
            "notes": "ignore",
        }

    return data


def _class_list(node) -> set[str]:
    cls = node.get("class", "")
    return {part for part in cls.split() if part}


def _tag_name(node) -> str:
    tag = getattr(node, "tag", "")
    if not isinstance(tag, str):
        return ""
    return XML_NAMESPACE_RE.sub("", tag).lower()


def _node_id(node) -> str | None:
    return node.get("data-sh-id")


def _node_path(node) -> str:
    parts: list[str] = []
    cur = node
    while cur is not None and len(parts) < 6:
        if not isinstance(cur.tag, str):
            cur = cur.getparent() if hasattr(cur, "getparent") else None
            continue
        label = _tag_name(cur)
        node_id = cur.get("data-sh-id")
        if node_id:
            label = f"{label}#{node_id}"
        parts.append(label)
        cur = cur.getparent() if hasattr(cur, "getparent") else None
    return " / ".join(reversed(parts))


def _add_issue(
    report: ValidationReport,
    severity: str,
    code: str,
    message: str,
    node=None,
) -> None:
    issue = ValidationIssue(
        severity=severity,
        code=code,
        message=message,
        node_id=_node_id(node) if node is not None else None,
        path=_node_path(node) if node is not None else None,
    )
    if severity == "error":
        report.errors.append(issue)
    else:
        report.warnings.append(issue)


def _parse_style(style: str | None) -> dict[str, str]:
    if not style:
        return {}
    out: dict[str, str] = {}
    for part in style.split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        out[key.strip().lower()] = value.strip()
    return out


def _is_dsl_document(text: str) -> bool:
    return "data-sh-dsl=" in text or "data-sh-kind=" in text or "sh-slide" in text


def _parse_html(html_text: str) -> ET.Element:
    try:
        return ET.fromstring(html_text)
    except ET.ParseError:
        return ET.fromstring(f"<fragment>{html_text}</fragment>")


def _iter_descendants(node):
    for child in list(node):
        yield child
        yield from _iter_descendants(child)


def _descendants_with_tag(node, tag_names: set[str]):
    for child in _iter_descendants(node):
        if _tag_name(child) in tag_names:
            yield child


def _validate_export_chain(
    report: ValidationReport,
    node,
    export_value: str | None,
    attr_name: str,
) -> None:
    if not export_value:
        return
    parts = [part.strip() for part in export_value.split(">") if part.strip()]
    if not parts:
        _add_issue(report, "error", "export.chain.empty", f"{attr_name} is empty", node)
        return
    invalid = [part for part in parts if part not in ALLOWED_EXPORT_MODES]
    if invalid:
        _add_issue(
            report,
            "error",
            "export.chain.invalid",
            f"{attr_name} contains unsupported export mode(s): {', '.join(invalid)}",
            node,
        )


def _validate_manifest_shape(report: ValidationReport, manifest: dict[str, Any]) -> None:
    if manifest.get("dsl") != DSL_VERSION:
        _add_issue(
            report,
            "error",
            "manifest.dsl",
            f"manifest.dsl must equal {DSL_VERSION}",
        )

    template_id = manifest.get("templateId")
    if not isinstance(template_id, str) or not template_id.strip():
        _add_issue(report, "error", "manifest.template_id", "manifest.templateId is required")

    slide = _as_dict(manifest.get("slide"))
    for key, minimum in DEFAULT_SLIDE_SIZE.items():
        value = slide.get(key)
        if not isinstance(value, int) or value < minimum:
            _add_issue(
                report,
                "error",
                f"slide.{key}",
                f"slide.{key} must be an integer >= {minimum}",
            )

    allowed_kinds = manifest.get("allowedKinds")
    if not isinstance(allowed_kinds, list) or not allowed_kinds:
        _add_issue(
            report,
            "error",
            "manifest.allowed_kinds",
            "manifest.allowedKinds must be a non-empty list",
        )
    else:
        seen: set[str] = set()
        for kind in allowed_kinds:
            if kind not in KNOWN_KINDS:
                _add_issue(
                    report,
                    "error",
                    "manifest.kind.invalid",
                    f"unsupported kind in manifest.allowedKinds: {kind!r}",
                )
            if kind in seen:
                _add_issue(
                    report,
                    "error",
                    "manifest.kind.duplicate",
                    f"duplicate allowed kind: {kind!r}",
                )
            seen.add(kind)

    default_export = _as_dict(manifest.get("defaultExport"))
    for kind, chain in default_export.items():
        if kind not in KNOWN_KINDS:
            _add_issue(
                report,
                "warning",
                "manifest.default_export.kind",
                f"defaultExport contains unknown kind: {kind!r}",
            )
            continue
        if not isinstance(chain, str):
            _add_issue(
                report,
                "error",
                "manifest.default_export.chain",
                f"defaultExport[{kind!r}] must be a string",
            )
            continue
        _validate_export_chain(report, None, chain, f"defaultExport[{kind!r}]")

    roles = _as_dict(manifest.get("roles"))
    allowed_roles = set(manifest.get("allowedRoles") or [])
    for role_name, role_spec in roles.items():
        spec = _as_dict(role_spec)
        if allowed_roles and role_name not in allowed_roles:
            _add_issue(
                report,
                "warning",
                "manifest.role.unlisted",
                f"role {role_name!r} is not listed in allowedRoles",
            )
        kind = spec.get("kind")
        if kind is not None and kind not in KNOWN_KINDS:
            _add_issue(
                report,
                "error",
                "manifest.role.kind",
                f"role {role_name!r} has unsupported kind {kind!r}",
            )
        fit = spec.get("fit")
        if fit is not None and fit not in FIT_MODES:
            _add_issue(
                report,
                "error",
                "manifest.role.fit",
                f"role {role_name!r} has unsupported fit mode {fit!r}",
            )
        export = spec.get("export")
        if isinstance(export, str):
            _validate_export_chain(report, None, export, f"roles[{role_name!r}].export")
        elif export is not None:
            _add_issue(
                report,
                "error",
                "manifest.role.export",
                f"role {role_name!r} export must be a string",
            )

        max_lines = spec.get("maxLines")
        if max_lines is not None and (not isinstance(max_lines, int) or max_lines < 1):
            _add_issue(
                report,
                "error",
                "manifest.role.max_lines",
                f"role {role_name!r} maxLines must be a positive integer",
            )

        allowed_child_roles = spec.get("allowedChildRoles")
        if allowed_child_roles is not None:
            if not isinstance(allowed_child_roles, list):
                _add_issue(
                    report,
                    "error",
                    "manifest.role.allowed_child_roles",
                    f"role {role_name!r} allowedChildRoles must be a list",
                )
            elif len(set(allowed_child_roles)) != len(allowed_child_roles):
                _add_issue(
                    report,
                    "error",
                    "manifest.role.allowed_child_roles.duplicate",
                    f"role {role_name!r} allowedChildRoles contains duplicates",
                )

    pptx_template = manifest.get("pptxTemplate")
    if not isinstance(pptx_template, str) or not pptx_template.strip():
        _add_issue(
            report,
            "error",
            "manifest.pptx_template",
            "manifest.pptxTemplate is required",
        )

    placeholders = _as_dict(manifest.get("placeholders"))
    if not placeholders:
        _add_issue(
            report,
            "error",
            "manifest.placeholders",
            "manifest.placeholders must be a non-empty object",
        )
    for placeholder_name, placeholder_spec in placeholders.items():
        spec = _as_dict(placeholder_spec)
        idx = spec.get("idx")
        kind = spec.get("kind")
        if not isinstance(idx, int) or idx < 0:
            _add_issue(
                report,
                "error",
                "manifest.placeholder.idx",
                f"placeholder {placeholder_name!r} idx must be a non-negative integer",
            )
        if kind not in SUPPORTED_PLACEHOLDER_KINDS:
            _add_issue(
                report,
                "error",
                "manifest.placeholder.kind",
                f"placeholder {placeholder_name!r} has unsupported kind {kind!r}",
            )

    placeholder_map = _as_dict(manifest.get("placeholderMap"))
    if not placeholder_map:
        _add_issue(
            report,
            "error",
            "manifest.placeholder_map",
            "manifest.placeholderMap must be a non-empty object",
        )
    for role_name, placeholder_name in placeholder_map.items():
        if allowed_roles and role_name not in allowed_roles:
            _add_issue(
                report,
                "warning",
                "manifest.placeholder_map.role",
                f"placeholderMap references unknown role {role_name!r}",
            )
        if placeholder_name not in placeholders:
            _add_issue(
                report,
                "error",
                "manifest.placeholder_map.target",
                f"placeholderMap references unknown placeholder {placeholder_name!r}",
            )


class SlideHTMLValidator:
    def __init__(self, manifest: Mapping[str, Any] | Any):
        self.manifest = _normalize_manifest_dict(_as_dict(manifest))

    def validate_manifest(self) -> ValidationReport:
        report = ValidationReport()
        _validate_manifest_shape(report, self.manifest)
        return report

    def validate_html(self, html_text: str) -> ValidationReport:
        report = ValidationReport()

        try:
            root = _parse_html(html_text)
        except Exception as exc:
            _add_issue(report, "error", "html.parse", f"HTML parse failed: {exc}")
            return report

        _validate_manifest_shape(report, self.manifest)

        deck_roots = self._find_deck_roots(root)
        if deck_roots:
            for deck_root in deck_roots:
                self._validate_deck_root(report, deck_root)
            return report

        slide_roots = self._find_slide_roots(root)
        if slide_roots:
            self._validate_inline_slide_roots(report, slide_roots)
            return report

        _add_issue(
            report,
            "error",
            "deck.root",
            "root must be a slide fragment or <article class='sh-deck'> with data-sh-dsl='slidehtml/v1'",
        )

        return report

    def _find_deck_roots(self, root):
        matches = []
        for node in [root, *_iter_descendants(root)]:
            if _tag_name(node) != "article":
                continue
            if "sh-deck" in _class_list(node):
                matches.append(node)
        return matches

    def _find_slide_roots(self, deck_root):
        slides = []
        for node in [deck_root, *_iter_descendants(deck_root)]:
            if _tag_name(node) != "section":
                continue
            if "sh-slide" in _class_list(node):
                slides.append(node)
        return slides

    def _validate_deck_root(self, report: ValidationReport, deck_root) -> None:
        dsl = deck_root.get("data-sh-dsl")
        if dsl != DSL_VERSION:
            _add_issue(
                report,
                "error",
                "deck.dsl",
                f"deck root must declare data-sh-dsl='{DSL_VERSION}'",
                deck_root,
            )

        slide_roots = self._find_slide_roots(deck_root)
        if not slide_roots:
            _add_issue(
                report,
                "error",
                "slide.missing",
                "at least one <section class='sh-slide'> is required",
                deck_root,
            )
            return

        seen_ids: set[str] = set()
        for slide in slide_roots:
            strict_export = deck_root.get(EXPORT_MODE_ATTR) == STRICT_EXPORT_MODE or slide.get(EXPORT_MODE_ATTR) == STRICT_EXPORT_MODE
            slide_id = slide.get("data-sh-id")
            template_id = slide.get("data-sh-template")
            size = slide.get("data-sh-size")
            legacy_template = slide.get("data-template")

            if not slide_id:
                _add_issue(
                    report,
                    "error",
                    "slide.id.missing",
                    "slide root requires data-sh-id",
                    slide,
                )
            elif slide_id in seen_ids:
                _add_issue(
                    report,
                    "error",
                    "slide.id.duplicate",
                    f"duplicate slide id {slide_id!r}",
                    slide,
                )
            else:
                seen_ids.add(slide_id)

            if not template_id:
                _add_issue(
                    report,
                    "error",
                    "slide.template.missing",
                    "slide root requires data-sh-template",
                    slide,
                )
            if legacy_template and template_id and legacy_template != template_id:
                _add_issue(
                    report,
                    "error",
                    "slide.template.mismatch",
                    "data-template and data-sh-template must match",
                    slide,
                )

            self._validate_slide_size(report, slide, size)
            self._validate_nodes(report, slide, seen_ids, strict_export=strict_export)

    def _validate_inline_slide_roots(
        self, report: ValidationReport, slide_roots: list
    ) -> None:
        seen_ids: set[str] = set()
        for slide in slide_roots:
            strict_export = slide.get(EXPORT_MODE_ATTR) == STRICT_EXPORT_MODE
            slide_id = slide.get("data-sh-id")
            template_id = slide.get("data-sh-template")
            size = slide.get("data-sh-size")
            legacy_template = slide.get("data-template")

            if not slide_id:
                _add_issue(
                    report,
                    "error",
                    "slide.id.missing",
                    "slide root requires data-sh-id",
                    slide,
                )
            elif slide_id in seen_ids:
                _add_issue(
                    report,
                    "error",
                    "slide.id.duplicate",
                    f"duplicate slide id {slide_id!r}",
                    slide,
                )
            else:
                seen_ids.add(slide_id)

            if not template_id:
                _add_issue(
                    report,
                    "error",
                    "slide.template.missing",
                    "slide root requires data-sh-template",
                    slide,
                )
            if legacy_template and template_id and legacy_template != template_id:
                _add_issue(
                    report,
                    "error",
                    "slide.template.mismatch",
                    "data-template and data-sh-template must match",
                    slide,
                )

            self._validate_slide_size(report, slide, size)
            self._validate_nodes(report, slide, seen_ids, strict_export=strict_export)

    def _validate_slide_size(
        self, report: ValidationReport, slide, size_value: str | None
    ) -> None:
        slide_spec = _as_dict(self.manifest.get("slide"))
        width = slide_spec.get("width")
        height = slide_spec.get("height")
        if not size_value:
            _add_issue(
                report,
                "error",
                "slide.size.missing",
                "slide root requires data-sh-size",
                slide,
            )
            return

        match = re.fullmatch(r"(\d+)x(\d+)", size_value.strip())
        if not match:
            _add_issue(
                report,
                "error",
                "slide.size.format",
                "data-sh-size must look like '1280x720'",
                slide,
            )
            return

        size_width = int(match.group(1))
        size_height = int(match.group(2))
        if isinstance(width, int) and size_width != width:
            _add_issue(
                report,
                "error",
                "slide.size.width",
                f"data-sh-size width {size_width} does not match manifest {width}",
                slide,
            )
        if isinstance(height, int) and size_height != height:
            _add_issue(
                report,
                "error",
                "slide.size.height",
                f"data-sh-size height {size_height} does not match manifest {height}",
                slide,
            )

    def _validate_nodes(
        self,
        report: ValidationReport,
        slide,
        seen_ids: set[str],
        *,
        strict_export: bool = False,
    ) -> None:
        manifest_roles = _as_dict(self.manifest.get("roles"))
        allowed_roles = set(self.manifest.get("allowedRoles") or [])
        allowed_classes = set(self.manifest.get("allowedClasses") or [])

        for node in slide.iter():
            if node is slide:
                continue
            tag = _tag_name(node)
            if not tag:
                continue
            if tag not in ALLOWED_TAGS:
                _add_issue(
                    report,
                    "error",
                    "tag.disallowed",
                    f"tag <{tag}> is not allowed",
                    node,
                )
            if tag == "script" and node.get("type") != "application/json":
                _add_issue(
                    report,
                    "error",
                    "script.disallowed",
                    "only script[type='application/json'] is allowed",
                    node,
                )

            node_id = node.get("data-sh-id")
            if node_id:
                if node_id in seen_ids:
                    _add_issue(
                        report,
                        "error",
                        "id.duplicate",
                        f"duplicate data-sh-id {node_id!r}",
                        node,
                    )
                else:
                    seen_ids.add(node_id)

            self._validate_node_classes(report, node, allowed_classes)
            kind = node.get("data-sh-kind")
            if not kind:
                continue
            if kind not in KNOWN_KINDS:
                _add_issue(
                    report,
                    "error",
                    "kind.invalid",
                    f"unsupported kind {kind!r}",
                    node,
                )
                continue

            export_mode = node.get("data-sh-export")
            fallback_chain = node.get("data-sh-fallback")
            if export_mode:
                _validate_export_chain(report, node, export_mode, "data-sh-export")
            else:
                _add_issue(
                    report,
                    "warning",
                    "export.missing",
                    "exportable nodes should declare data-sh-export",
                    node,
                )
            if fallback_chain:
                _validate_export_chain(report, node, fallback_chain, "data-sh-fallback")

            role = node.get("data-sh-role")
            if role:
                if allowed_roles and role not in allowed_roles:
                    _add_issue(
                        report,
                        "error",
                        "role.invalid",
                        f"unsupported role {role!r}",
                        node,
                    )
                role_spec = manifest_roles.get(role)
                if role_spec:
                    self._validate_role_alignment(report, node, role, role_spec)
            elif kind == "text" and manifest_roles:
                _add_issue(
                    report,
                    "warning",
                    "role.missing",
                    "text nodes should declare data-sh-role",
                    node,
                )

            if kind in EXPORTABLE_KINDS and not node.get("data-sh-id"):
                _add_issue(
                    report,
                    "error" if strict_export else "warning",
                    "id.missing.strict" if strict_export else "id.missing",
                    "exportable node should declare data-sh-id before normalization",
                    node,
                )

            if export_mode == "placeholder":
                placeholder = node.get("data-sh-placeholder")
                if not placeholder:
                    _add_issue(
                        report,
                        "error",
                        "placeholder.missing",
                        "placeholder export requires data-sh-placeholder",
                        node,
                    )
                elif placeholder not in _as_dict(self.manifest.get("placeholders")):
                    _add_issue(
                        report,
                        "error",
                        "placeholder.unknown",
                        f"unknown placeholder {placeholder!r}",
                        node,
                    )

            if kind in EXPORTABLE_KINDS:
                if not export_mode:
                    _add_issue(
                        report,
                        "error" if strict_export else "warning",
                        "export.missing.strict" if strict_export else "export.missing",
                        "exportable nodes should declare data-sh-export",
                        node,
                    )
                elif strict_export and export_mode == "auto":
                    _add_issue(
                        report,
                        "error",
                        "export.auto.strict",
                        "normalized export HTML must resolve data-sh-export before export",
                        node,
                    )
                if strict_export and not node.get("data-sh-fallback"):
                    _add_issue(
                        report,
                        "error",
                        "export.fallback.missing",
                        "normalized export HTML must declare data-sh-fallback",
                        node,
                    )

            if kind == "text":
                self._validate_text_node(report, node, strict_export=strict_export)
            elif kind == "shape":
                self._validate_shape_node(report, node)
            elif kind == "image":
                self._validate_image_node(report, node)
            elif kind == "chart":
                self._validate_chart_node(report, node, strict_export=strict_export)
            elif kind == "table":
                self._validate_table_node(report, node)
            elif kind == "line":
                self._validate_line_node(report, node)

    def _validate_node_classes(
        self, report: ValidationReport, node, allowed_classes: set[str]
    ) -> None:
        for cls in sorted(_class_list(node)):
            if cls in STRUCTURAL_CLASSES or cls.startswith("sh-"):
                continue
            if cls.startswith(("tpl-", "tok-", "role-", "var-", "u-")):
                if allowed_classes and cls not in allowed_classes:
                    _add_issue(
                        report,
                        "warning",
                        "class.unknown",
                        f"class '{cls}' not in manifest",
                        node,
                    )

    def _validate_role_alignment(
        self, report: ValidationReport, node, role_name: str, role_spec: dict[str, Any]
    ) -> None:
        kind = role_spec.get("kind")
        if kind is not None and node.get("data-sh-kind") != kind:
            _add_issue(
                report,
                "error",
                "role.kind.mismatch",
                f"role {role_name!r} expects kind {kind!r}",
                node,
            )
        fit = role_spec.get("fit")
        if fit is not None and node.get("data-sh-fit") != fit:
            _add_issue(
                report,
                "warning",
                "role.fit.mismatch",
                f"role {role_name!r} prefers fit mode {fit!r}",
                node,
            )
        max_lines = role_spec.get("maxLines")
        if max_lines is not None:
            try:
                node_lines = int(node.get("data-sh-max-lines") or "0")
            except ValueError:
                node_lines = 0
            if node_lines and node_lines > int(max_lines):
                _add_issue(
                    report,
                    "warning",
                    "role.max_lines.exceeded",
                    f"role {role_name!r} prefers maxLines <= {max_lines}",
                    node,
                )
        min_font = role_spec.get("minFont")
        max_font = role_spec.get("maxFont")
        for attr_name, attr_value, code in (
            ("data-sh-min-font", min_font, "role.min_font.mismatch"),
            ("data-sh-max-font", max_font, "role.max_font.mismatch"),
        ):
            if attr_value is not None and node.get(attr_name):
                try:
                    node_value = int(node.get(attr_name) or "0")
                except ValueError:
                    node_value = 0
                if node_value and node_value != int(attr_value):
                    _add_issue(
                        report,
                        "warning",
                        code,
                        f"role {role_name!r} prefers {attr_name}={attr_value}",
                        node,
                    )
        export = role_spec.get("export")
        if isinstance(export, str) and node.get("data-sh-export"):
            _validate_export_chain(report, node, node.get("data-sh-export"), "data-sh-export")

    def _validate_text_node(self, report: ValidationReport, node, *, strict_export: bool = False) -> None:
        fit = node.get("data-sh-fit")
        if not fit:
            _add_issue(
                report,
                "error",
                "text.fit.missing",
                "text nodes require data-sh-fit",
                node,
            )
        elif fit not in FIT_MODES:
            _add_issue(
                report,
                "error",
                "text.fit.invalid",
                f"unsupported fit mode {fit!r}",
                node,
            )
        elif strict_export and fit not in STRICT_EXPORT_FIT_MODES:
            _add_issue(
                report,
                "error",
                "text.fit.invalid.strict",
                f"normalized export HTML only allows fit modes {sorted(STRICT_EXPORT_FIT_MODES)}",
                node,
            )

        max_lines = node.get("data-sh-max-lines")
        if not max_lines:
            _add_issue(
                report,
                "error",
                "text.max_lines.missing",
                "text nodes require data-sh-max-lines",
                node,
            )
        else:
            try:
                if int(max_lines) < 1:
                    raise ValueError
            except ValueError:
                _add_issue(
                    report,
                    "error",
                    "text.max_lines.invalid",
                    f"unsupported max-lines value {max_lines!r}",
                    node,
                )

        for attr_name, code in (
            ("data-sh-min-font", "text.min_font.invalid"),
            ("data-sh-max-font", "text.max_font.invalid"),
        ):
            value = node.get(attr_name)
            if not value:
                continue
            try:
                if int(value) < 1:
                    raise ValueError
            except ValueError:
                _add_issue(
                    report,
                    "error",
                    code,
                    f"unsupported font constraint value {value!r}",
                    node,
                )

        for child in _iter_descendants(node):
            tag = _tag_name(child)
            if tag not in TEXT_ALLOWED_TAGS:
                _add_issue(
                    report,
                    "error",
                    "text.tag.invalid",
                    f"text node contains invalid tag <{tag}>",
                    child,
                )

    def _validate_shape_node(self, report: ValidationReport, node) -> None:
        if not node.get("data-sh-shape"):
            _add_issue(
                report,
                "error",
                "shape.missing",
                "shape nodes require data-sh-shape",
                node,
            )

    def _validate_image_node(self, report: ValidationReport, node) -> None:
        src = node.get("src") or node.get("data-sh-src") or node.get("data-sh-rendered-src")
        if not src:
            _add_issue(
                report,
                "error",
                "image.src.missing",
                "image nodes require src or data-sh-src",
                node,
            )
        fit = node.get("data-sh-fit")
        if fit and fit not in {"cover", "contain", "stretch"}:
            _add_issue(
                report,
                "error",
                "image.fit.invalid",
                f"unsupported image fit mode {fit!r}",
                node,
            )

    def _validate_chart_node(self, report: ValidationReport, node, *, strict_export: bool = False) -> None:
        if not node.get("data-sh-chart-kind"):
            _add_issue(
                report,
                "error",
                "chart.kind.missing",
                "chart nodes require data-sh-chart-kind",
                node,
            )

        scripts = [
            child
            for child in list(node)
            if _tag_name(child) == "script"
            and child.get("type") == "application/json"
        ]
        if len(scripts) != 1:
            _add_issue(
                report,
                "error",
                "chart.json.missing",
                "chart nodes require exactly one JSON script child",
                node,
            )
            return

        if strict_export:
            preview_children = [
                child
                for child in list(node)
                if _tag_name(child) != "script" or child.get("type") != "application/json"
            ]
            if preview_children:
                _add_issue(
                    report,
                    "error",
                    "chart.preview.dom",
                    "normalized export HTML must not contain preview scaffold DOM inside chart nodes",
                    node,
                )
                return

        try:
            payload = json.loads(scripts[0].text or "{}")
        except Exception as exc:
            _add_issue(
                report,
                "error",
                "chart.json.invalid",
                f"invalid chart JSON: {exc}",
                scripts[0],
            )
            return

        if "series" not in payload:
            _add_issue(
                report,
                "error",
                "chart.series.missing",
                "chart JSON requires series",
                scripts[0],
            )

    def _validate_table_node(self, report: ValidationReport, node) -> None:
        if _tag_name(node) != "table":
            _add_issue(
                report,
                "error",
                "table.tag.invalid",
                "table kind must use <table>",
                node,
            )
        if not any(
            _tag_name(child) in {"thead", "tbody"}
            for child in list(node)
        ):
            _add_issue(
                report,
                "warning",
                "table.structure.weak",
                "table nodes should use thead/tbody",
                node,
            )

        for cell in _descendants_with_tag(node, {"td", "th"}):
            for desc in _iter_descendants(cell):
                tag = _tag_name(desc)
                if tag not in TABLE_ALLOWED_CELL_TAGS:
                    _add_issue(
                        report,
                        "error",
                        "table.cell.tag.invalid",
                        f"table cells may not contain <{tag}>",
                        desc,
                    )

    def _validate_line_node(self, report: ValidationReport, node) -> None:
        if node.get("data-sh-line-kind") and node.get("data-sh-line-kind") not in {
            "straight",
            "elbow",
            "curve",
        }:
            _add_issue(
                report,
                "error",
                "line.kind.invalid",
                f"unsupported line kind {node.get('data-sh-line-kind')!r}",
                node,
            )
        if not node.get("data-sh-from"):
            _add_issue(
                report,
                "error",
                "line.from.missing",
                "line nodes require data-sh-from",
                node,
            )
        if not node.get("data-sh-to"):
            _add_issue(
                report,
                "error",
                "line.to.missing",
                "line nodes require data-sh-to",
                node,
            )


def validate_manifest(manifest: Mapping[str, Any] | Any) -> ValidationReport:
    return SlideHTMLValidator(manifest).validate_manifest()


def validate_html(html_text: str, manifest: Mapping[str, Any] | Any) -> ValidationReport:
    return SlideHTMLValidator(manifest).validate_html(html_text)


def validate_export_html(html_text: str, manifest: Mapping[str, Any] | Any) -> ValidationReport:
    return SlideHTMLValidator(manifest).validate_html(html_text)


def is_slidehtml_document(html_text: str) -> bool:
    return _is_dsl_document(html_text)
