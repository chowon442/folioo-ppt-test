from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from functools import lru_cache

from app.config import get_project_root, settings
from app.models.slidehtml import TemplateManifest, ThemeManifest

logger = logging.getLogger(__name__)

# 갤러리 CSS 스코핑: `.slide--foo` 같은 BEM 수정자 안의 `.slide` 는 치환하면 안 됨 (\.slide(?!--)\b)
_GALLERY_SLIDE_SELECTOR = re.compile(r"\.slide(?!--)\b")


def _gallery_scope_selector(theme_id: str) -> str:
    """갤러리 HTML: `.template-gallery-page` 안의 `.theme-gallery-scope--<id>` 에 맞춤 (특이성↑)."""
    return f".template-gallery-page .theme-gallery-scope--{theme_id}"


def _strip_css_comments_for_gallery(css: str) -> str:
    """블록 주석 제거. 문자열 리터럴 안의 `/*` 는 주석으로 취급하지 않음 (치환 전에 호출)."""
    result: list[str] = []
    i = 0
    n = len(css)
    while i < n:
        c = css[i]
        if c in ("'", '"'):
            q = c
            result.append(c)
            i += 1
            while i < n:
                if css[i] == "\\" and i + 1 < n:
                    result.append(css[i])
                    result.append(css[i + 1])
                    i += 2
                    continue
                result.append(css[i])
                if css[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and css[i + 1] == "*":
            i += 2
            while i < n - 1:
                if css[i] == "*" and css[i + 1] == "/":
                    i += 2
                    break
                i += 1
            continue
        result.append(c)
        i += 1
    return "".join(result)

_SLIDE_KIND_ORDER = (
    "cover",
    "skills",
    "timeline",
    "agenda",
    "project_card",
    "metrics_table",
    "bar_chart",
    "two_column",
    "closing",
    "quote",
)


def _candidate_slide_template_roots() -> list[Path]:
    """slide_templates 후보 디렉터리 (중복 제거, 순서 유지)."""
    roots: list[Path] = []
    # 0) 소스 파일 위치에서 상위로 올라가며 slide_templates/ 탐색 (uvicorn cwd·.env 와 무관)
    try:
        here = Path(__file__).resolve()
        for i, anc in enumerate(here.parents):
            if i >= 14:
                break
            roots.append((anc / "slide_templates").resolve())
    except Exception:
        pass
    # 1) 이 파일 기준 3단계 상위(일반적 레이아웃)
    roots.append(Path(__file__).resolve().parent.parent.parent / "slide_templates")
    # 2) pydantic 설정 (기본은 config 기준 프로젝트 루트/slide_templates)
    try:
        roots.append(Path(settings.slide_templates_dir).resolve())
    except Exception:
        pass
    try:
        roots.append((Path(settings.base_dir) / "slide_templates").resolve())
    except Exception:
        pass
    # 3) 현재 작업 디렉터리
    roots.append((Path.cwd() / "slide_templates").resolve())

    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        key = str(r)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _walk_up_find_slide_templates(start: Path) -> Path | None:
    """start 또는 상위 경로에서 slide_templates/ 를 찾는다 (cwd·서브폴더 실행 대응)."""
    try:
        cur = start.resolve()
    except OSError:
        return None
    for p in [cur] + list(cur.parents):
        cand = p / "slide_templates"
        if _root_has_usable_themes(cand):
            return cand
    return None


def _root_has_usable_themes(root: Path) -> bool:
    """themes/<id>/theme.json 이 하나라도 있거나, 레거시 flat 슬라이드가 있으면 True."""
    try:
        root = root.resolve()
    except OSError:
        return False
    try:
        if not root.is_dir():
            return False
    except OSError:
        return False
    themes = root / "themes"
    try:
        if themes.is_dir():
            for p in themes.iterdir():
                if p.is_dir() and (p / "theme.json").is_file():
                    return True
    except OSError:
        pass
    # 레거시: slide_templates/cover/manifest.json (themes 없음)
    try:
        for p in root.iterdir():
            if (
                p.is_dir()
                and p.name != "themes"
                and (p / "manifest.json").is_file()
            ):
                return True
    except OSError:
        pass
    return False


def _pick_slide_templates_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return Path(explicit).resolve()

    # 1) 현재 작업 디렉터리에서 위로 (uvicorn 실행 위치가 레포 루트가 아닐 때)
    found = _walk_up_find_slide_templates(Path.cwd())
    if found is not None:
        logger.info("slide_templates 경로 사용 (cwd 기준): %s", found)
        return found

    # 2) 이 모듈 파일 기준 상위로 (패키지가 실제로 있는 트리)
    found = _walk_up_find_slide_templates(Path(__file__).resolve().parent)
    if found is not None:
        logger.info("slide_templates 경로 사용 (__file__ 기준): %s", found)
        return found

    # 3) app.config 기준 프로젝트 루트 (.env 의 BASE_DIR / SLIDE_TEMPLATES_DIR 오염과 무관)
    try:
        cand = (get_project_root() / "slide_templates").resolve()
        if _root_has_usable_themes(cand):
            logger.info("slide_templates 경로 사용 (get_project_root): %s", cand)
            return cand
    except OSError:
        pass

    # 4) 기존 후보 목록 (settings 경로는 유효할 때만 채택)
    candidates = _candidate_slide_template_roots()
    for candidate in candidates:
        if _root_has_usable_themes(candidate):
            logger.info("slide_templates 경로 사용: %s", candidate)
            return candidate

    # 5) get_project_root 기준 폴더가 있으면 디렉터리만이라도 반환 (디버그·오류 메시지용)
    src_default = Path(__file__).resolve().parent.parent.parent / "slide_templates"
    try:
        if src_default.is_dir():
            logger.warning(
                "유효한 themes/ 를 찾지 못했습니다. 소스 기준 slide_templates 사용: %s",
                src_default,
            )
            return src_default
    except OSError:
        pass
    try:
        fallback = get_project_root() / "slide_templates"
        if fallback.is_dir():
            logger.warning(
                "유효한 themes/ 를 찾지 못했습니다. get_project_root 기준 폴더 사용: %s",
                fallback,
            )
            return fallback.resolve()
    except OSError:
        pass

    for candidate in candidates:
        try:
            if candidate.is_dir():
                logger.warning(
                    "slide_templates 가 테마 형식으로 인식되지 않습니다. 경로: %s",
                    candidate,
                )
                return candidate
        except OSError:
            continue

    logger.error(
        "slide_templates 디렉터리를 찾지 못했습니다. 후보: %s",
        candidates,
    )
    return src_default


class TemplateLoader:
    """slide_templates/themes/<theme_id>/theme.json + 슬라이드 종류별 폴더.

    레거시: slide_templates/<slide_kind>/ 에 직접 manifest 가 있는 경우
    가상 테마 default 로 취급한다.
    """

    def __init__(self, templates_dir: Path | None = None):
        self._dir = _pick_slide_templates_root(templates_dir)
        self.base_css.cache_clear()
        self.manifest.cache_clear()
        self.slide_html.cache_clear()
        self.style_css.cache_clear()

    def _themes_root(self) -> Path:
        return self._dir / "themes"

    def _legacy_flat_layout(self) -> bool:
        """themes/default 가 없고, 루트에 슬라이드 폴더만 있는 옛 구조."""
        td = self._themes_root() / "default"
        if td.is_dir() and (td / "theme.json").is_file():
            return False
        try:
            for p in self._dir.iterdir():
                if (
                    p.is_dir()
                    and p.name != "themes"
                    and (p / "manifest.json").is_file()
                ):
                    return True
        except OSError:
            pass
        return False

    def _theme_dir_for(self, theme_id: str) -> Path:
        if self._legacy_flat_layout() and theme_id == "default":
            return self._dir
        return self._themes_root() / theme_id

    def theme_ids(self) -> list[str]:
        root = self._themes_root()
        try:
            if root.is_dir():
                found = sorted(
                    p.name
                    for p in root.iterdir()
                    if p.is_dir() and (p / "theme.json").is_file()
                )
                if found:
                    return found
        except OSError:
            pass
        if self._legacy_flat_layout():
            return ["default"]
        return []

    @lru_cache(maxsize=1)
    def base_css(self) -> str:
        return (self._dir / "_base.css").read_text(encoding="utf-8")

    def theme_manifest(self, theme_id: str) -> ThemeManifest:
        path = self._themes_root() / theme_id / "theme.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return ThemeManifest(**data)
        if theme_id == "default" and self._legacy_flat_layout():
            return ThemeManifest(
                theme_id="default",
                name="SlideForge 기본",
                description="slide_templates/ 아래에 슬라이드 종류 폴더가 직접 있는 레거시 배치입니다.",
            )
        raise FileNotFoundError(f"theme.json 없음: {path}")

    def _theme_path(self, theme_id: str) -> Path:
        return self._theme_dir_for(theme_id)

    def slide_kind_ids(self, theme_id: str) -> list[str]:
        root = self._theme_path(theme_id)
        if not root.is_dir():
            return []
        raw = [
            p.name
            for p in root.iterdir()
            if p.is_dir() and (p / "manifest.json").is_file()
        ]
        priority = {n: i for i, n in enumerate(_SLIDE_KIND_ORDER)}
        return sorted(raw, key=lambda t: (priority.get(t, 1000), t))

    @lru_cache(maxsize=128)
    def manifest(self, theme_id: str, slide_kind_id: str) -> TemplateManifest:
        path = self._theme_path(theme_id) / slide_kind_id / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return TemplateManifest(**data)

    @lru_cache(maxsize=128)
    def slide_html(self, theme_id: str, slide_kind_id: str) -> str:
        path = self._theme_path(theme_id) / slide_kind_id / "slide.html"
        return path.read_text(encoding="utf-8")

    @lru_cache(maxsize=128)
    def style_css(self, theme_id: str, slide_kind_id: str) -> str:
        path = self._theme_path(theme_id) / slide_kind_id / "style.css"
        return path.read_text(encoding="utf-8")

    def all_css(self, theme_id: str) -> str:
        parts = [self.base_css()]
        for sk in self.slide_kind_ids(theme_id):
            parts.append(self.style_css(theme_id, sk))
        return "\n".join(parts)

    def _base_css_for_gallery(self, theme_id: str) -> str:
        """갤러리 전용: _base.css 내용을 테마 스코프 안에만 두어 전역 * 리셋이 페이지 전체를 망가뜨리지 않게 한다."""
        scope = _gallery_scope_selector(theme_id)
        return (
            f"{scope} *, {scope} *::before, {scope} *::after {{\n"
            f"    box-sizing: border-box;\n"
            f"    margin: 0;\n"
            f"    padding: 0;\n"
            f"}}\n"
            f"{scope} .slide {{\n"
            f"    width: 1280px;\n"
            f"    height: 720px;\n"
            f"    position: relative;\n"
            f"    overflow: hidden;\n"
            f"    font-family: 'Pretendard', Arial, sans-serif;\n"
            f"    font-size: 16px;\n"
            f"    line-height: 1.5;\n"
            f"    color: #222;\n"
            f"    -webkit-print-color-adjust: exact;\n"
            f"    print-color-adjust: exact;\n"
            f"    page-break-after: always;\n"
            f"}}\n"
            f"{scope} [data-slot] {{\n"
            f"    word-wrap: break-word;\n"
            f"    overflow-wrap: break-word;\n"
            f"}}\n"
        )

    def all_css_for_gallery(self, theme_id: str) -> str:
        """템플릿 갤러리(/template) 전용.

        한 페이지에 여러 테마 미리보기를 올릴 때, 동일한 `.slide[data-template=...]`
        선택자가 서로 덮어쓰이지 않도록 테마별 루트 클래스 아래로만 적용되게 한다.
        HTML 쪽에는 슬라이드 HTML을 감싸는 요소(예: `.slide-wrapper`)에
        `class="theme-gallery-scope--<theme_id>"` 가 있어야 한다.

        `_base.css`는 파일 그대로 합치지 않는다. 전역 `*` / `@import` 가 갤러리 상단바·본문 레이아웃을 깨뜨리기 때문이다.
        """
        scope = _gallery_scope_selector(theme_id)
        parts = [self._base_css_for_gallery(theme_id)]
        for sk in self.slide_kind_ids(theme_id):
            css = self.style_css(theme_id, sk)
            css = _strip_css_comments_for_gallery(css)
            css = _GALLERY_SLIDE_SELECTOR.sub(f"{scope} .slide", css)
            parts.append(css)
        return "\n".join(parts)

    def all_manifests(self, theme_id: str) -> dict[str, TemplateManifest]:
        return {
            sk: self.manifest(theme_id, sk)
            for sk in self.slide_kind_ids(theme_id)
        }

    def theme_template_name(self, theme_id: str) -> str:
        for manifest in self.all_manifests(theme_id).values():
            if manifest.pptx_template:
                candidate = Path(manifest.pptx_template)
                name = candidate.name.strip()
                if name:
                    return name
        return f"{theme_id}-theme-template.pptx"

    def build_prompt_reference(self, theme_id: str) -> str:
        sections = []
        for sk in self.slide_kind_ids(theme_id):
            m = self.manifest(theme_id, sk)
            html = self.slide_html(theme_id, sk)
            roles_table = []
            for rname, spec in m.roles.items():
                constraints = []
                if spec.max_length:
                    constraints.append(f"maxLength={spec.max_length}")
                if spec.max_lines:
                    constraints.append(f"maxLines={spec.max_lines}")
                if spec.max_items:
                    constraints.append(f"maxItems={spec.max_items}")
                req = "필수" if spec.required else "선택"
                constraints_str = ", ".join(constraints) if constraints else "-"
                roles_table.append(
                    f"  - {rname} (kind={spec.kind}, {req}, export={spec.export_chain}, {constraints_str})"
                )

            section = f"""### 슬라이드 종류: {m.template_id} ({m.name})
설명: {m.description}

역할:
{chr(10).join(roles_table)}

허용 kind:
{", ".join(m.allowed_kinds)}

참조 HTML:
```
{html.strip()}
```"""
            sections.append(section)

        return "\n\n".join(sections)


template_loader = TemplateLoader()
