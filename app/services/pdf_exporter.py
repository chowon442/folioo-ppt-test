from __future__ import annotations

import re

from app.services.playwright_node import run_playwright_job
from app.services.template_loader import template_loader


_REMOTE_IMPORT_RE = re.compile(r"@import\s+url\((?:'|\")?https?://[^)]+?\)\s*;?", re.IGNORECASE)


def _build_deck_html(slides_html: list[str], theme_id: str) -> str:
    all_css = _REMOTE_IMPORT_RE.sub("", template_loader.all_css(theme_id))
    slides_markup = "\n".join(slides_html)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
{all_css}

@page {{
    size: 1280px 720px;
    margin: 0;
}}
</style>
</head>
<body style="margin:0; padding:0;">
{slides_markup}
</body>
</html>"""


async def export_pdf(slides_html: list[str], theme_id: str = "default") -> bytes:
    html = _build_deck_html(slides_html, theme_id)
    pdf_bytes = await run_playwright_job(
        mode="pdf",
        html=html,
        viewport={"width": 1280, "height": 720},
        pdf_options={
            "width": "1280px",
            "height": "720px",
            "printBackground": True,
            "preferCSSPageSize": True,
        },
    )
    assert isinstance(pdf_bytes, bytes)
    return pdf_bytes
