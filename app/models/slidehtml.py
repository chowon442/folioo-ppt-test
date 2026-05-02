from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SlideHTMLKind = Literal[
    "layout",
    "group",
    "text",
    "shape",
    "image",
    "chart",
    "table",
    "line",
    "svg",
    "flatten",
    "notes",
]

SlideHTMLExportMode = Literal[
    "auto",
    "native",
    "placeholder",
    "svg",
    "png",
    "ignore",
]

SlideHTMLFitMode = Literal["none", "shrink", "truncate", "clip", "split"]

DEFAULT_EXPORT_CHAINS: dict[str, str] = {
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

LEGACY_TYPE_TO_KIND: dict[str, str] = {
    "text": "text",
    "richtext": "text",
    "list": "group",
    "image": "image",
    "chart": "chart",
    "table": "table",
}


def first_export_mode(chain: str | None, default: SlideHTMLExportMode = "auto") -> SlideHTMLExportMode:
    if not chain:
        return default
    mode = chain.split(">")[0].strip()
    if mode in {"auto", "native", "placeholder", "svg", "png", "ignore"}:
        return mode  # type: ignore[return-value]
    return default


class SlideCanvas(BaseModel):
    width: int = 1280
    height: int = 720
    grid: int = 4
    safe_area: list[int] | None = Field(default=None, alias="safeArea")

    model_config = ConfigDict(populate_by_name=True)

    @property
    def size_list(self) -> list[int]:
        return [self.width, self.height]


class SlideHTMLRoleSpec(BaseModel):
    kind: SlideHTMLKind = "text"
    required: bool = False
    fit: SlideHTMLFitMode | None = None
    max_lines: int | None = Field(default=None, alias="maxLines")
    min_font: int | None = Field(default=None, alias="minFont")
    max_font: int | None = Field(default=None, alias="maxFont")
    max_length: int | None = Field(default=None, alias="maxLength")
    max_items: int | None = Field(default=None, alias="maxItems")
    token_class: str | None = Field(default=None, alias="tokenClass")
    export: str | None = None
    placeholder: str | None = None
    valign: Literal["top", "middle", "bottom"] | None = None
    allowed_child_roles: list[str] | None = Field(
        default=None, alias="allowedChildRoles"
    )
    allowed_child_tags: list[str] | None = Field(
        default=None, alias="allowedChildTags"
    )

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        if "minFont" not in data and "minFontPx" in data:
            data["minFont"] = data["minFontPx"]
        if "maxFont" not in data and "maxFontPx" in data:
            data["maxFont"] = data["maxFontPx"]
        return data

    @property
    def export_chain(self) -> str:
        return self.export or DEFAULT_EXPORT_CHAINS[self.kind]


class SlideHTMLAssetSpec(BaseModel):
    path: str
    kind: str = "image"


class SlideHTMLPlaceholderSpec(BaseModel):
    idx: int
    kind: Literal["text", "image", "chart", "table"]
    name: str | None = None


class SlideHTMLChartTemplateSpec(BaseModel):
    kind: str
    description: str | None = None
    style: dict[str, Any] = Field(default_factory=dict)


class TemplateManifest(BaseModel):
    dsl: str = "slidehtml/v1"
    version: str = "1.0.0"
    template_id: str = Field(alias="templateId")
    name: str
    description: str
    slide: SlideCanvas
    allowed_kinds: list[SlideHTMLKind] = Field(default_factory=list, alias="allowedKinds")
    allowed_roles: list[str] = Field(default_factory=list, alias="allowedRoles")
    allowed_classes: list[str] = Field(default_factory=list, alias="allowedClasses")
    default_export: dict[str, str] = Field(default_factory=dict, alias="defaultExport")
    roles: dict[str, SlideHTMLRoleSpec] = Field(default_factory=dict)
    assets: dict[str, SlideHTMLAssetSpec] = Field(default_factory=dict)
    placeholders: dict[str, SlideHTMLPlaceholderSpec] = Field(default_factory=dict)
    chart_templates: dict[str, SlideHTMLChartTemplateSpec] = Field(
        default_factory=dict, alias="chartTemplates"
    )
    pptx_template: str | None = Field(default=None, alias="pptxTemplate")
    placeholder_map: dict[str, str] = Field(default_factory=dict, alias="placeholderMap")
    chart_style_template: str | None = Field(default=None, alias="chartStyleTemplate")
    table_style_template: dict[str, Any] = Field(default_factory=dict, alias="tableStyleTemplate")
    role_constraints: dict[str, SlideHTMLRoleSpec] = Field(
        default_factory=dict, alias="roleConstraints"
    )
    theme: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw

        data = dict(raw)

        if "templateId" not in data and "template_id" in data:
            data["templateId"] = data["template_id"]

        if "slide" not in data and "slide_size" in data:
            size = list(data["slide_size"])
            width = int(size[0]) if len(size) > 0 else 1280
            height = int(size[1]) if len(size) > 1 else 720
            data["slide"] = {"width": width, "height": height, "grid": 4}

        data.setdefault("dsl", "slidehtml/v1")
        data.setdefault("version", "1.0.0")

        legacy_slots = data.get("slots") or {}
        roles = dict(data.get("roles") or {})

        if legacy_slots and not roles:
            converted_roles: dict[str, dict[str, Any]] = {}
            derived_roles: list[str] = []
            derived_kinds: set[str] = set()

            for role_name, spec in legacy_slots.items():
                slot_type = str(spec.get("type") or "text").lower()
                kind = LEGACY_TYPE_TO_KIND.get(slot_type, "text")
                export_mode = str(spec.get("export_mode") or "text").lower()
                export_chain = DEFAULT_EXPORT_CHAINS.get(kind, "native>png")
                if export_mode in {"flatten", "svg", "png", "placeholder", "ignore", "native"}:
                    export_chain = export_mode

                converted_roles[role_name] = {
                    "kind": kind,
                    "required": bool(spec.get("required", False)),
                    "fit": "truncate" if kind == "text" else None,
                    "maxLines": spec.get("max_lines"),
                    "maxLength": spec.get("max_length"),
                    "maxItems": spec.get("max_items"),
                    "allowedChildTags": spec.get("allowed_child_tags"),
                    "export": export_chain,
                }
                derived_roles.append(role_name)
                derived_kinds.add(kind)

            data["roles"] = converted_roles
            data.setdefault("allowedRoles", derived_roles)
            if "allowedKinds" not in data:
                data["allowedKinds"] = sorted(derived_kinds)

        if "allowedKinds" not in data or not data["allowedKinds"]:
            data["allowedKinds"] = sorted(
                {
                    role.get("kind", "text")
                    if isinstance(role, dict)
                    else "text"
                    for role in (data.get("roles") or {}).values()
                }
                | {"layout", "group", "text", "shape", "image", "chart", "table", "line", "svg", "flatten", "notes"}
            )

        if "allowedRoles" not in data or not data["allowedRoles"]:
            data["allowedRoles"] = list((data.get("roles") or {}).keys())

        if "defaultExport" not in data or not data["defaultExport"]:
            default_export: dict[str, str] = dict(DEFAULT_EXPORT_CHAINS)
            for role in (data.get("roles") or {}).values():
                if not isinstance(role, dict):
                    continue
                kind = role.get("kind")
                if kind and role.get("export") and kind not in default_export:
                    default_export[kind] = role["export"]
            data["defaultExport"] = default_export

        return data

    @property
    def slide_size(self) -> list[int]:
        return self.slide.size_list

    def export_chain_for_kind(self, kind: str) -> str:
        return self.default_export.get(kind, DEFAULT_EXPORT_CHAINS.get(kind, "native>png"))

    def role_spec(self, role_name: str | None) -> SlideHTMLRoleSpec | None:
        if not role_name:
            return None
        return self.role_constraints.get(role_name) or self.roles.get(role_name)


class ThemeManifest(BaseModel):
    theme_id: str
    name: str
    description: str
