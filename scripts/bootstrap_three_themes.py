"""
slide_templates/themes/ 아래에 테마 3종(paper_light, coral_energy, forest_moss)을 생성합니다.
각 테마는 default와 동일한 9종 + quote 1종 = 10종 슬라이드가 있습니다.
실행: 프로젝트 루트에서  python scripts/bootstrap_three_themes.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEMES_DIR = ROOT / "slide_templates" / "themes"
DEFAULT = THEMES_DIR / "default"

QUOTE_MANIFEST = {
    "template_id": "quote",
    "name": "인용구 슬라이드",
    "description": "미션·비전·핵심 메시지를 인용구 형식으로 강조한다.",
    "slide_size": [1280, 720],
    "slots": {
        "title": {
            "type": "text",
            "max_length": 40,
            "max_lines": 1,
            "required": False,
            "export_mode": "text",
        },
        "quote": {
            "type": "text",
            "max_length": 280,
            "max_lines": 6,
            "required": True,
            "export_mode": "text",
        },
        "attribution": {
            "type": "text",
            "max_length": 80,
            "max_lines": 2,
            "required": False,
            "export_mode": "text",
        },
    },
}

QUOTE_HTML = """<section class="slide" data-template="quote">
    <div class="qt-inner">
        <p class="qt-kicker" data-slot="title" data-export="text">핵심 메시지</p>
        <blockquote class="qt-text" data-slot="quote" data-export="text">
            미션과 가치를 한 줄로 전달하는 인용문이 들어갑니다.
        </blockquote>
        <cite class="qt-from" data-slot="attribution" data-export="text">— 출처</cite>
    </div>
</section>
"""

KINDS = (
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

THEME_META = {
    "paper_light": {
        "theme_id": "paper_light",
        "name": "페이퍼 라이트",
        "description": "밝은 종이 질감과 코발트 포인트. 에디토리얼·학술 발표에 적합합니다.",
    },
    "coral_energy": {
        "theme_id": "coral_energy",
        "name": "코랄 에너지",
        "description": "웜 코랄·앰버 그라데이션. 스타트업·프로덕트 데모에 활기찬 분위기를 줍니다.",
    },
    "forest_moss": {
        "theme_id": "forest_moss",
        "name": "포레스트 모스",
        "description": "딥 그린과 민트 악센트. 지속가능·헬스·테크에 차분한 신뢰감을 줍니다.",
    },
}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def _write_quote(theme_dir: Path) -> None:
    d = theme_dir / "quote"
    d.mkdir(parents=True, exist_ok=True)
    _write_json(d / "manifest.json", QUOTE_MANIFEST)
    (d / "slide.html").write_text(QUOTE_HTML.strip() + "\n", encoding="utf-8")


def _css_paper_light() -> dict[str, str]:
    """밝은 페이퍼 + 블루 악센트."""
    p = {
        "bg": "#fafaf9",
        "bg2": "#f5f5f4",
        "card": "#ffffff",
        "border": "#e7e5e4",
        "text": "#1c1917",
        "muted": "#78716c",
        "accent": "#2563eb",
        "accent_soft": "#93c5fd",
        "sidebar": "#1e3a8a",
        "sidebar_muted": "#bfdbfe",
        "cover_grad": "linear-gradient(145deg, #fafaf9 0%, #e0e7ff 55%, #f8fafc 100%)",
        "glow": "rgba(37, 99, 235, 0.12)",
    }
    return {
        "cover": f""".slide[data-template="cover"] {{
    background: {p["cover_grad"]};
    display: flex;
    align-items: center;
    justify-content: center;
}}
.slide[data-template="cover"] .cover-bg {{
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 75% 25%, {p["glow"]} 0%, transparent 55%),
        radial-gradient(circle at 20% 80%, rgba(14, 165, 233, 0.08) 0%, transparent 50%);
    pointer-events: none;
}}
.slide[data-template="cover"] .cover-content {{
    position: relative;
    z-index: 1;
    text-align: center;
    padding: 0 120px;
}}
.slide[data-template="cover"] .cover-title {{
    font-size: 48px;
    font-weight: 700;
    color: {p["text"]};
    line-height: 1.3;
    margin-bottom: 24px;
    letter-spacing: -0.02em;
}}
.slide[data-template="cover"] .cover-subtitle {{
    font-size: 20px;
    font-weight: 400;
    color: {p["muted"]};
    line-height: 1.6;
    margin-bottom: 40px;
}}
.slide[data-template="cover"] .cover-author {{
    font-size: 16px;
    font-weight: 500;
    color: {p["muted"]};
    display: inline-block;
    padding: 8px 24px;
    border: 1px solid {p["border"]};
    border-radius: 24px;
    background: {p["card"]};
}}
""",
        "skills": f""".slide[data-template="skills"] {{
    background: {p["bg"]};
    display: flex;
    flex-direction: column;
    padding: 48px 60px;
}}
.slide[data-template="skills"] .sk-title {{
    font-size: 32px;
    font-weight: 700;
    color: {p["text"]};
    position: relative;
    padding-bottom: 16px;
}}
.slide[data-template="skills"] .sk-title::after {{
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    width: 48px;
    height: 4px;
    background: {p["accent"]};
    border-radius: 2px;
}}
.slide[data-template="skills"] .sk-grid {{
    flex: 1;
    display: flex;
    gap: 32px;
}}
.slide[data-template="skills"] .sk-group {{
    flex: 1;
    background: {p["card"]};
    border-radius: 12px;
    padding: 28px 24px;
    border: 1px solid {p["border"]};
}}
.slide[data-template="skills"] .sk-group-title {{
    font-size: 15px;
    font-weight: 700;
    color: {p["accent"]};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 2px solid {p["border"]};
}}
.slide[data-template="skills"] .sk-items span {{
    display: inline-block;
    padding: 8px 16px;
    background: {p["bg2"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    color: {p["text"]};
}}
""",
        "timeline": f""".slide[data-template="timeline"] {{
    background: linear-gradient(180deg, {p["bg"]} 0%, {p["bg2"]} 100%);
    display: flex;
    flex-direction: column;
    padding: 48px 60px;
}}
.slide[data-template="timeline"] .tl-title {{
    font-size: 32px;
    font-weight: 700;
    color: {p["text"]};
}}
.slide[data-template="timeline"] .tl-track::before {{
    content: '';
    position: absolute;
    top: 18px;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, {p["accent"]}, {p["accent_soft"]});
    opacity: 0.5;
}}
.slide[data-template="timeline"] .tl-dot {{
    background: {p["accent"]};
    border: 3px solid {p["card"]};
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.25);
}}
.slide[data-template="timeline"] .tl-card {{
    background: {p["card"]};
    border: 1px solid {p["border"]};
    border-radius: 12px;
    padding: 20px;
}}
.slide[data-template="timeline"] .tl-date {{
    color: {p["accent"]};
}}
.slide[data-template="timeline"] .tl-role {{
    color: {p["text"]};
}}
.slide[data-template="timeline"] .tl-desc {{
    color: {p["muted"]};
}}
""",
        "agenda": f""".slide[data-template="agenda"] {{
    background: linear-gradient(160deg, {p["bg2"]} 0%, {p["bg"]} 50%, #eef2ff 100%);
    display: flex;
    align-items: stretch;
}}
.slide[data-template="agenda"] .agenda-bg {{
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, rgba(37, 99, 235, 0.08) 0%, transparent 45%),
        radial-gradient(ellipse 80% 60% at 100% 0%, rgba(14, 165, 233, 0.06), transparent);
    pointer-events: none;
}}
.slide[data-template="agenda"] .agenda-inner {{
    position: relative;
    z-index: 1;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 64px 96px 64px 88px;
}}
.slide[data-template="agenda"] .agenda-title {{
    font-size: 40px;
    font-weight: 800;
    color: {p["text"]};
    letter-spacing: -0.03em;
    margin-bottom: 36px;
}}
.slide[data-template="agenda"] .agenda-list li {{
    color: {p["text"]};
    padding-left: 36px;
}}
.slide[data-template="agenda"] .agenda-list li::before {{
    content: "";
    position: absolute;
    left: 0;
    top: 0.55em;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: linear-gradient(135deg, {p["accent"]}, #38bdf8);
}}
""",
        "project_card": f""".slide[data-template="project_card"] {{
    background: {p["bg"]};
    display: flex;
}}
.slide[data-template="project_card"] .pc-sidebar {{
    width: 320px;
    background: {p["sidebar"]};
    padding: 48px 32px;
}}
.slide[data-template="project_card"] .pc-role {{
    color: {p["accent_soft"]};
}}
.slide[data-template="project_card"] .pc-period {{
    color: {p["sidebar_muted"]};
}}
.slide[data-template="project_card"] .pc-tech span {{
    color: #f1f5f9;
    background: rgba(255, 255, 255, 0.12);
}}
.slide[data-template="project_card"] .pc-name {{
    color: {p["text"]};
}}
.slide[data-template="project_card"] .pc-summary {{
    color: {p["muted"]};
}}
.slide[data-template="project_card"] .pc-highlights li {{
    color: {p["text"]};
    background: {p["card"]};
    border-left: 3px solid {p["accent"]};
}}
""",
        "metrics_table": f""".slide[data-template="metrics_table"] {{
    background: linear-gradient(160deg, {p["bg"]} 0%, #eef2ff 45%, {p["bg2"]} 100%);
    color: {p["text"]};
    padding: 48px 56px 40px;
    display: flex;
    flex-direction: column;
    gap: 24px;
}}
.slide[data-template="metrics_table"] .mt-title {{
    color: {p["text"]};
}}
.slide[data-template="metrics_table"] .mt-subtitle {{
    color: {p["muted"]};
}}
.slide[data-template="metrics_table"] .mt-table {{
    box-shadow: 0 4px 24px rgba(15, 23, 42, 0.08);
}}
.slide[data-template="metrics_table"] .mt-table thead {{
    background: linear-gradient(90deg, rgba(37, 99, 235, 0.2), rgba(59, 130, 246, 0.15));
}}
.slide[data-template="metrics_table"] .mt-table th {{
    color: {p["accent"]};
    border-bottom: 1px solid {p["border"]};
}}
.slide[data-template="metrics_table"] .mt-table td {{
    color: {p["text"]};
    border-bottom: 1px solid {p["border"]};
    background: {p["card"]};
}}
.slide[data-template="metrics_table"] .mt-table tbody tr:nth-child(even) td {{
    background: {p["bg2"]};
}}
.slide[data-template="metrics_table"] .mt-table strong {{
    color: {p["accent"]};
}}
.slide[data-template="metrics_table"] .mt-footnote {{
    color: {p["muted"]};
}}
""",
        "bar_chart": f""".slide[data-template="bar_chart"] {{
    background: radial-gradient(ellipse 120% 80% at 20% 20%, rgba(37, 99, 235, 0.12), transparent 55%),
        radial-gradient(ellipse 90% 70% at 85% 75%, rgba(14, 165, 233, 0.1), transparent 50%),
        {p["bg2"]};
    color: {p["text"]};
    padding: 44px 52px 36px;
    display: flex;
    flex-direction: column;
    gap: 20px;
}}
.slide[data-template="bar_chart"] .bc-title {{
    color: {p["text"]};
}}
.slide[data-template="bar_chart"] .bc-subtitle {{
    color: {p["muted"]};
}}
.slide[data-template="bar_chart"] .bc-bars text {{
    fill: {p["text"]};
}}
.slide[data-template="bar_chart"] .bc-svg line {{
    stroke: {p["border"]};
}}
.slide[data-template="bar_chart"] .bc-footnote {{
    color: {p["muted"]};
}}
""",
        "two_column": f""".slide[data-template="two_column"] {{
    background: {p["card"]};
    display: flex;
    flex-direction: column;
    padding: 48px 60px 32px;
}}
.slide[data-template="two_column"] .tc-title {{
    color: {p["text"]};
}}
.slide[data-template="two_column"] .tc-accent-line {{
    background: {p["accent"]};
}}
.slide[data-template="two_column"] .tc-left,
.slide[data-template="two_column"] .tc-right {{
    color: {p["text"]};
}}
.slide[data-template="two_column"] .tc-divider {{
    background: {p["border"]};
}}
.slide[data-template="two_column"] .tc-footer {{
    border-top: 1px solid {p["border"]};
}}
.slide[data-template="two_column"] .tc-footnote {{
    color: {p["muted"]};
}}
""",
        "closing": f""".slide[data-template="closing"] {{
    background: linear-gradient(135deg, #e0e7ff 0%, {p["bg"]} 50%, #dbeafe 100%);
    display: flex;
    align-items: center;
    justify-content: center;
}}
.slide[data-template="closing"] .cl-bg {{
    position: absolute;
    inset: 0;
    background:
        radial-gradient(circle at 30% 50%, rgba(37, 99, 235, 0.1) 0%, transparent 50%),
        radial-gradient(circle at 70% 50%, rgba(14, 165, 233, 0.08) 0%, transparent 50%);
    pointer-events: none;
}}
.slide[data-template="closing"] .cl-message {{
    color: {p["text"]};
}}
.slide[data-template="closing"] .cl-subtitle {{
    color: {p["muted"]};
}}
.slide[data-template="closing"] .cl-contact {{
    color: {p["accent"]};
    border: 1px solid rgba(37, 99, 235, 0.35);
}}
""",
        "quote": f""".slide[data-template="quote"] {{
    background: {p["card"]};
    display: flex;
    align-items: center;
    justify-content: center;
    border-left: 6px solid {p["accent"]};
}}
.slide[data-template="quote"] .qt-inner {{
    max-width: 920px;
    padding: 0 72px;
}}
.slide[data-template="quote"] .qt-kicker {{
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {p["accent"]};
    margin-bottom: 20px;
}}
.slide[data-template="quote"] .qt-text {{
    font-size: 32px;
    font-weight: 600;
    line-height: 1.45;
    color: {p["text"]};
    margin: 0 0 24px;
    font-style: italic;
}}
.slide[data-template="quote"] .qt-from {{
    font-size: 16px;
    color: {p["muted"]};
    font-style: normal;
}}
""",
    }


def _css_coral_energy() -> dict[str, str]:
    """웜 다크 + 코랄·오렌지."""
    p = {
        "bg": "#1c1917",
        "bg2": "#292524",
        "card": "#44403c",
        "border": "#57534e",
        "text": "#fafaf9",
        "muted": "#a8a29e",
        "accent": "#f97316",
        "accent2": "#fb7185",
        "sidebar": "#431407",
        "sidebar_muted": "#fdba74",
        "glow": "rgba(249, 115, 22, 0.25)",
    }
    return {
        "cover": f""".slide[data-template="cover"] {{
    background: linear-gradient(135deg, #292524 0%, #431407 40%, #1c1917 100%);
    display: flex;
    align-items: center;
    justify-content: center;
}}
.slide[data-template="cover"] .cover-bg {{
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 70% 30%, {p["glow"]} 0%, transparent 55%),
        radial-gradient(circle at 30% 80%, rgba(251, 113, 133, 0.12) 0%, transparent 50%);
    pointer-events: none;
}}
.slide[data-template="cover"] .cover-content {{
    position: relative;
    z-index: 1;
    text-align: center;
    padding: 0 120px;
}}
.slide[data-template="cover"] .cover-title {{
    font-size: 48px;
    font-weight: 700;
    color: {p["text"]};
    line-height: 1.3;
    margin-bottom: 24px;
}}
.slide[data-template="cover"] .cover-subtitle {{
    font-size: 20px;
    color: {p["muted"]};
    margin-bottom: 40px;
}}
.slide[data-template="cover"] .cover-author {{
    font-size: 16px;
    color: {p["muted"]};
    display: inline-block;
    padding: 8px 24px;
    border: 1px solid {p["border"]};
    border-radius: 24px;
}}
""",
        "skills": f""".slide[data-template="skills"] {{
    background: {p["bg"]};
    display: flex;
    flex-direction: column;
    padding: 48px 60px;
}}
.slide[data-template="skills"] .sk-title {{
    font-size: 32px;
    font-weight: 700;
    color: {p["text"]};
    padding-bottom: 16px;
}}
.slide[data-template="skills"] .sk-title::after {{
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    width: 48px;
    height: 4px;
    background: {p["accent"]};
    border-radius: 2px;
}}
.slide[data-template="skills"] .sk-header {{
    margin-bottom: 40px;
    position: relative;
}}
.slide[data-template="skills"] .sk-title {{
    position: relative;
}}
.slide[data-template="skills"] .sk-grid {{
    flex: 1;
    display: flex;
    gap: 32px;
}}
.slide[data-template="skills"] .sk-group {{
    flex: 1;
    background: {p["bg2"]};
    border-radius: 12px;
    padding: 28px 24px;
    border: 1px solid {p["border"]};
}}
.slide[data-template="skills"] .sk-group-title {{
    font-size: 15px;
    font-weight: 700;
    color: {p["accent2"]};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 2px solid {p["border"]};
}}
.slide[data-template="skills"] .sk-items span {{
    padding: 8px 16px;
    background: {p["card"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    font-size: 14px;
    color: {p["text"]};
}}
""",
        "timeline": f""".slide[data-template="timeline"] {{
    background: linear-gradient(180deg, {p["bg"]} 0%, {p["bg2"]} 100%);
    display: flex;
    flex-direction: column;
    padding: 48px 60px;
}}
.slide[data-template="timeline"] .tl-title {{
    color: {p["text"]};
}}
.slide[data-template="timeline"] .tl-track::before {{
    height: 2px;
    background: linear-gradient(90deg, {p["accent"]}, {p["accent2"]});
    opacity: 0.55;
}}
.slide[data-template="timeline"] .tl-dot {{
    background: {p["accent"]};
    border: 3px solid {p["bg"]};
    box-shadow: 0 0 0 2px rgba(249, 115, 22, 0.35);
}}
.slide[data-template="timeline"] .tl-card {{
    background: rgba(68, 64, 60, 0.6);
    border: 1px solid {p["border"]};
    border-radius: 12px;
    padding: 20px;
}}
.slide[data-template="timeline"] .tl-date {{
    color: {p["accent2"]};
}}
.slide[data-template="timeline"] .tl-role {{
    color: {p["text"]};
}}
.slide[data-template="timeline"] .tl-desc {{
    color: {p["muted"]};
}}
""",
        "agenda": f""".slide[data-template="agenda"] {{
    background: linear-gradient(160deg, #1c1917 0%, #431407 45%, {p["bg"]} 100%);
    display: flex;
    align-items: stretch;
}}
.slide[data-template="agenda"] .agenda-bg {{
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, rgba(249, 115, 22, 0.15) 0%, transparent 45%),
        radial-gradient(ellipse 80% 60% at 100% 0%, rgba(251, 113, 133, 0.1), transparent);
    pointer-events: none;
}}
.slide[data-template="agenda"] .agenda-inner {{
    position: relative;
    z-index: 1;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 64px 96px 64px 88px;
}}
.slide[data-template="agenda"] .agenda-title {{
    font-size: 40px;
    font-weight: 800;
    color: {p["text"]};
    margin-bottom: 36px;
}}
.slide[data-template="agenda"] .agenda-list li {{
    color: #e7e5e4;
    padding-left: 36px;
}}
.slide[data-template="agenda"] .agenda-list li::before {{
    content: "";
    position: absolute;
    left: 0;
    top: 0.55em;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: linear-gradient(135deg, {p["accent"]}, {p["accent2"]});
}}
""",
        "project_card": f""".slide[data-template="project_card"] {{
    background: {p["bg2"]};
    display: flex;
}}
.slide[data-template="project_card"] .pc-sidebar {{
    width: 320px;
    background: {p["sidebar"]};
    padding: 48px 32px;
}}
.slide[data-template="project_card"] .pc-role {{
    color: {p["accent2"]};
}}
.slide[data-template="project_card"] .pc-period {{
    color: {p["sidebar_muted"]};
}}
.slide[data-template="project_card"] .pc-tech span {{
    color: #fff7ed;
    background: rgba(255, 255, 255, 0.1);
}}
.slide[data-template="project_card"] .pc-main {{
    background: {p["bg"]};
}}
.slide[data-template="project_card"] .pc-name {{
    color: {p["text"]};
}}
.slide[data-template="project_card"] .pc-summary {{
    color: {p["muted"]};
}}
.slide[data-template="project_card"] .pc-highlights li {{
    color: {p["text"]};
    background: {p["card"]};
    border-left: 3px solid {p["accent"]};
}}
""",
        "metrics_table": f""".slide[data-template="metrics_table"] {{
    background: linear-gradient(160deg, {p["bg"]} 0%, #431407 40%, {p["bg2"]} 100%);
    color: {p["text"]};
    padding: 48px 56px 40px;
    display: flex;
    flex-direction: column;
    gap: 24px;
}}
.slide[data-template="metrics_table"] .mt-title {{
    color: {p["text"]};
}}
.slide[data-template="metrics_table"] .mt-subtitle {{
    color: {p["muted"]};
}}
.slide[data-template="metrics_table"] .mt-table {{
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
}}
.slide[data-template="metrics_table"] .mt-table thead {{
    background: linear-gradient(90deg, rgba(249, 115, 22, 0.35), rgba(251, 113, 133, 0.2));
}}
.slide[data-template="metrics_table"] .mt-table th {{
    color: #ffedd5;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}}
.slide[data-template="metrics_table"] .mt-table td {{
    color: {p["text"]};
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(28, 25, 23, 0.65);
}}
.slide[data-template="metrics_table"] .mt-table tbody tr:nth-child(even) td {{
    background: rgba(68, 64, 60, 0.45);
}}
.slide[data-template="metrics_table"] .mt-table strong {{
    color: {p["accent2"]};
}}
.slide[data-template="metrics_table"] .mt-footnote {{
    color: {p["muted"]};
}}
""",
        "bar_chart": f""".slide[data-template="bar_chart"] {{
    background: radial-gradient(ellipse 120% 80% at 20% 20%, rgba(249, 115, 22, 0.2), transparent 55%),
        radial-gradient(ellipse 90% 70% at 85% 75%, rgba(251, 113, 133, 0.12), transparent 50%),
        #0c0a09;
    color: {p["text"]};
    padding: 44px 52px 36px;
    display: flex;
    flex-direction: column;
    gap: 20px;
}}
.slide[data-template="bar_chart"] .bc-title {{
    color: {p["text"]};
}}
.slide[data-template="bar_chart"] .bc-subtitle {{
    color: {p["muted"]};
}}
.slide[data-template="bar_chart"] .bc-footnote {{
    color: {p["muted"]};
}}
""",
        "two_column": f""".slide[data-template="two_column"] {{
    background: {p["bg2"]};
    display: flex;
    flex-direction: column;
    padding: 48px 60px 32px;
}}
.slide[data-template="two_column"] .tc-title {{
    color: {p["text"]};
}}
.slide[data-template="two_column"] .tc-accent-line {{
    background: {p["accent"]};
}}
.slide[data-template="two_column"] .tc-left,
.slide[data-template="two_column"] .tc-right {{
    color: #d6d3d1;
}}
.slide[data-template="two_column"] .tc-divider {{
    background: {p["border"]};
}}
.slide[data-template="two_column"] .tc-footer {{
    border-top: 1px solid {p["border"]};
}}
.slide[data-template="two_column"] .tc-footnote {{
    color: {p["muted"]};
}}
""",
        "closing": f""".slide[data-template="closing"] {{
    background: linear-gradient(135deg, #1c1917 0%, #431407 50%, #1c1917 100%);
    display: flex;
    align-items: center;
    justify-content: center;
}}
.slide[data-template="closing"] .cl-bg {{
    position: absolute;
    inset: 0;
    background:
        radial-gradient(circle at 30% 50%, rgba(249, 115, 22, 0.15) 0%, transparent 50%),
        radial-gradient(circle at 70% 50%, rgba(251, 113, 133, 0.1) 0%, transparent 50%);
    pointer-events: none;
}}
.slide[data-template="closing"] .cl-message {{
    color: {p["text"]};
}}
.slide[data-template="closing"] .cl-subtitle {{
    color: {p["muted"]};
}}
.slide[data-template="closing"] .cl-contact {{
    color: {p["accent2"]};
    border: 1px solid rgba(251, 113, 133, 0.35);
}}
""",
        "quote": f""".slide[data-template="quote"] {{
    background: linear-gradient(90deg, {p["sidebar"]} 0%, {p["bg2"]} 100%);
    display: flex;
    align-items: center;
    justify-content: center;
}}
.slide[data-template="quote"] .qt-inner {{
    max-width: 920px;
    padding: 0 72px;
}}
.slide[data-template="quote"] .qt-kicker {{
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {p["accent"]};
    margin-bottom: 20px;
}}
.slide[data-template="quote"] .qt-text {{
    font-size: 32px;
    font-weight: 600;
    line-height: 1.45;
    color: {p["text"]};
    margin: 0 0 24px;
    font-style: italic;
}}
.slide[data-template="quote"] .qt-from {{
    font-size: 16px;
    color: {p["muted"]};
    font-style: normal;
}}
""",
    }


def _css_forest_moss() -> dict[str, str]:
    """딥 그린 + 민트 악센트."""
    p = {
        "bg": "#052e16",
        "bg2": "#064e3b",
        "card": "#065f46",
        "border": "#047857",
        "text": "#ecfdf5",
        "muted": "#6ee7b7",
        "accent": "#34d399",
        "accent2": "#10b981",
        "sidebar": "#022c22",
        "sidebar_muted": "#a7f3d0",
        "glow": "rgba(52, 211, 153, 0.2)",
    }
    return {
        "cover": f""".slide[data-template="cover"] {{
    background: linear-gradient(135deg, {p["bg"]} 0%, {p["bg2"]} 50%, #022c22 100%);
    display: flex;
    align-items: center;
    justify-content: center;
}}
.slide[data-template="cover"] .cover-bg {{
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 65% 35%, {p["glow"]} 0%, transparent 55%),
        radial-gradient(circle at 25% 75%, rgba(16, 185, 129, 0.12) 0%, transparent 50%);
    pointer-events: none;
}}
.slide[data-template="cover"] .cover-content {{
    position: relative;
    z-index: 1;
    text-align: center;
    padding: 0 120px;
}}
.slide[data-template="cover"] .cover-title {{
    font-size: 48px;
    font-weight: 700;
    color: {p["text"]};
    line-height: 1.3;
    margin-bottom: 24px;
}}
.slide[data-template="cover"] .cover-subtitle {{
    font-size: 20px;
    color: {p["muted"]};
    margin-bottom: 40px;
}}
.slide[data-template="cover"] .cover-author {{
    font-size: 16px;
    color: {p["muted"]};
    display: inline-block;
    padding: 8px 24px;
    border: 1px solid {p["border"]};
    border-radius: 24px;
}}
""",
        "skills": f""".slide[data-template="skills"] {{
    background: {p["bg"]};
    display: flex;
    flex-direction: column;
    padding: 48px 60px;
}}
.slide[data-template="skills"] .sk-header {{
    margin-bottom: 40px;
    position: relative;
}}
.slide[data-template="skills"] .sk-title {{
    font-size: 32px;
    font-weight: 700;
    color: {p["text"]};
    position: relative;
    padding-bottom: 16px;
}}
.slide[data-template="skills"] .sk-title::after {{
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    width: 48px;
    height: 4px;
    background: {p["accent"]};
    border-radius: 2px;
}}
.slide[data-template="skills"] .sk-grid {{
    flex: 1;
    display: flex;
    gap: 32px;
}}
.slide[data-template="skills"] .sk-group {{
    flex: 1;
    background: rgba(6, 78, 59, 0.55);
    border-radius: 12px;
    padding: 28px 24px;
    border: 1px solid {p["border"]};
}}
.slide[data-template="skills"] .sk-group-title {{
    font-size: 15px;
    font-weight: 700;
    color: {p["accent2"]};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 2px solid {p["border"]};
}}
.slide[data-template="skills"] .sk-items span {{
    padding: 8px 16px;
    background: {p["bg"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    font-size: 14px;
    color: {p["text"]};
}}
""",
        "timeline": f""".slide[data-template="timeline"] {{
    background: linear-gradient(180deg, {p["bg"]} 0%, {p["bg2"]} 100%);
    display: flex;
    flex-direction: column;
    padding: 48px 60px;
}}
.slide[data-template="timeline"] .tl-title {{
    color: {p["text"]};
}}
.slide[data-template="timeline"] .tl-track::before {{
    height: 2px;
    background: linear-gradient(90deg, {p["accent"]}, {p["accent2"]});
    opacity: 0.55;
}}
.slide[data-template="timeline"] .tl-dot {{
    background: {p["accent"]};
    border: 3px solid {p["bg"]};
    box-shadow: 0 0 0 2px rgba(52, 211, 153, 0.35);
}}
.slide[data-template="timeline"] .tl-card {{
    background: rgba(6, 95, 70, 0.45);
    border: 1px solid {p["border"]};
    border-radius: 12px;
    padding: 20px;
}}
.slide[data-template="timeline"] .tl-date {{
    color: {p["accent2"]};
}}
.slide[data-template="timeline"] .tl-role {{
    color: {p["text"]};
}}
.slide[data-template="timeline"] .tl-desc {{
    color: {p["muted"]};
}}
""",
        "agenda": f""".slide[data-template="agenda"] {{
    background: linear-gradient(160deg, {p["bg"]} 0%, #064e3b 45%, {p["bg2"]} 100%);
    display: flex;
    align-items: stretch;
}}
.slide[data-template="agenda"] .agenda-bg {{
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, rgba(52, 211, 153, 0.12) 0%, transparent 45%),
        radial-gradient(ellipse 80% 60% at 100% 0%, rgba(16, 185, 129, 0.1), transparent);
    pointer-events: none;
}}
.slide[data-template="agenda"] .agenda-inner {{
    position: relative;
    z-index: 1;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 64px 96px 64px 88px;
}}
.slide[data-template="agenda"] .agenda-title {{
    font-size: 40px;
    font-weight: 800;
    color: {p["text"]};
    margin-bottom: 36px;
}}
.slide[data-template="agenda"] .agenda-list li {{
    color: #d1fae5;
    padding-left: 36px;
}}
.slide[data-template="agenda"] .agenda-list li::before {{
    content: "";
    position: absolute;
    left: 0;
    top: 0.55em;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: linear-gradient(135deg, {p["accent"]}, {p["accent2"]});
}}
""",
        "project_card": f""".slide[data-template="project_card"] {{
    background: {p["bg2"]};
    display: flex;
}}
.slide[data-template="project_card"] .pc-sidebar {{
    width: 320px;
    background: {p["sidebar"]};
    padding: 48px 32px;
}}
.slide[data-template="project_card"] .pc-role {{
    color: {p["accent2"]};
}}
.slide[data-template="project_card"] .pc-period {{
    color: {p["sidebar_muted"]};
}}
.slide[data-template="project_card"] .pc-tech span {{
    color: #ecfdf5;
    background: rgba(255, 255, 255, 0.08);
}}
.slide[data-template="project_card"] .pc-main {{
    background: {p["bg"]};
}}
.slide[data-template="project_card"] .pc-name {{
    color: {p["text"]};
}}
.slide[data-template="project_card"] .pc-summary {{
    color: {p["muted"]};
}}
.slide[data-template="project_card"] .pc-highlights li {{
    color: {p["text"]};
    background: rgba(6, 78, 59, 0.5);
    border-left: 3px solid {p["accent"]};
}}
""",
        "metrics_table": f""".slide[data-template="metrics_table"] {{
    background: linear-gradient(160deg, {p["bg"]} 0%, #064e3b 45%, {p["bg2"]} 100%);
    color: {p["text"]};
    padding: 48px 56px 40px;
    display: flex;
    flex-direction: column;
    gap: 24px;
}}
.slide[data-template="metrics_table"] .mt-title {{
    color: {p["text"]};
}}
.slide[data-template="metrics_table"] .mt-subtitle {{
    color: {p["muted"]};
}}
.slide[data-template="metrics_table"] .mt-table thead {{
    background: linear-gradient(90deg, rgba(52, 211, 153, 0.3), rgba(16, 185, 129, 0.2));
}}
.slide[data-template="metrics_table"] .mt-table th {{
    color: #a7f3d0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}}
.slide[data-template="metrics_table"] .mt-table td {{
    color: {p["text"]};
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(5, 46, 22, 0.55);
}}
.slide[data-template="metrics_table"] .mt-table tbody tr:nth-child(even) td {{
    background: rgba(6, 78, 59, 0.45);
}}
.slide[data-template="metrics_table"] .mt-table strong {{
    color: {p["accent2"]};
}}
.slide[data-template="metrics_table"] .mt-footnote {{
    color: {p["muted"]};
}}
""",
        "bar_chart": f""".slide[data-template="bar_chart"] {{
    background: radial-gradient(ellipse 120% 80% at 20% 20%, rgba(52, 211, 153, 0.18), transparent 55%),
        radial-gradient(ellipse 90% 70% at 85% 75%, rgba(16, 185, 129, 0.12), transparent 50%),
        #041f15;
    color: {p["text"]};
    padding: 44px 52px 36px;
    display: flex;
    flex-direction: column;
    gap: 20px;
}}
.slide[data-template="bar_chart"] .bc-title {{
    color: {p["text"]};
}}
.slide[data-template="bar_chart"] .bc-subtitle {{
    color: {p["muted"]};
}}
.slide[data-template="bar_chart"] .bc-footnote {{
    color: {p["muted"]};
}}
""",
        "two_column": f""".slide[data-template="two_column"] {{
    background: {p["bg2"]};
    display: flex;
    flex-direction: column;
    padding: 48px 60px 32px;
}}
.slide[data-template="two_column"] .tc-title {{
    color: {p["text"]};
}}
.slide[data-template="two_column"] .tc-accent-line {{
    background: {p["accent"]};
}}
.slide[data-template="two_column"] .tc-left,
.slide[data-template="two_column"] .tc-right {{
    color: #d1fae5;
}}
.slide[data-template="two_column"] .tc-divider {{
    background: {p["border"]};
}}
.slide[data-template="two_column"] .tc-footer {{
    border-top: 1px solid {p["border"]};
}}
.slide[data-template="two_column"] .tc-footnote {{
    color: {p["muted"]};
}}
""",
        "closing": f""".slide[data-template="closing"] {{
    background: linear-gradient(135deg, {p["bg"]} 0%, {p["bg2"]} 50%, #022c22 100%);
    display: flex;
    align-items: center;
    justify-content: center;
}}
.slide[data-template="closing"] .cl-bg {{
    position: absolute;
    inset: 0;
    background:
        radial-gradient(circle at 30% 50%, rgba(52, 211, 153, 0.15) 0%, transparent 50%),
        radial-gradient(circle at 70% 50%, rgba(16, 185, 129, 0.1) 0%, transparent 50%);
    pointer-events: none;
}}
.slide[data-template="closing"] .cl-message {{
    color: {p["text"]};
}}
.slide[data-template="closing"] .cl-subtitle {{
    color: {p["muted"]};
}}
.slide[data-template="closing"] .cl-contact {{
    color: {p["accent2"]};
    border: 1px solid rgba(52, 211, 153, 0.35);
}}
""",
        "quote": f""".slide[data-template="quote"] {{
    background: linear-gradient(100deg, {p["sidebar"]} 0%, {p["bg2"]} 100%);
    display: flex;
    align-items: center;
    justify-content: center;
}}
.slide[data-template="quote"] .qt-inner {{
    max-width: 920px;
    padding: 0 72px;
}}
.slide[data-template="quote"] .qt-kicker {{
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {p["accent2"]};
    margin-bottom: 20px;
}}
.slide[data-template="quote"] .qt-text {{
    font-size: 32px;
    font-weight: 600;
    line-height: 1.45;
    color: {p["text"]};
    margin: 0 0 24px;
    font-style: italic;
}}
.slide[data-template="quote"] .qt-from {{
    font-size: 16px;
    color: {p["muted"]};
    font-style: normal;
}}
""",
    }


CSS_BUILDERS = {
    "paper_light": _css_paper_light,
    "coral_energy": _css_coral_energy,
    "forest_moss": _css_forest_moss,
}


def build_theme(theme_id: str) -> None:
    if theme_id not in THEME_META:
        raise ValueError(theme_id)
    td = THEMES_DIR / theme_id
    if td.is_dir():
        shutil.rmtree(td)
    shutil.copytree(DEFAULT, td)

    meta = THEME_META[theme_id]
    _write_json(td / "theme.json", meta)

    _write_quote(td)

    css_map = CSS_BUILDERS[theme_id]()
    for kind in KINDS:
        if kind == "quote":
            (td / "quote" / "style.css").write_text(
                css_map["quote"].strip() + "\n", encoding="utf-8"
            )
            continue
        base = (DEFAULT / kind / "style.css").read_text(encoding="utf-8")
        merged = (
            base
            + "\n\n/* --- theme override: "
            + theme_id
            + " --- */\n"
            + css_map[kind].strip()
            + "\n"
        )
        (td / kind / "style.css").write_text(merged, encoding="utf-8")


def main() -> None:
    if not DEFAULT.is_dir():
        raise SystemExit(f"default 테마 없음: {DEFAULT}")
    for tid in ("paper_light", "coral_energy", "forest_moss"):
        build_theme(tid)
        print(f"OK: {tid} (10 slide kinds)")


if __name__ == "__main__":
    main()
