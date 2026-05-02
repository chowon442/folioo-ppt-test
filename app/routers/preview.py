from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.store import deck_store
from app.services.template_loader import template_loader

router = APIRouter(tags=["preview"])

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "web_templates"))


def _infer_public_port(request: Request) -> int:
    """브라우저와 동일한 기본 포트(80/443) 보정."""
    p = request.url.port
    if p is None:
        return 443 if request.url.scheme == "https" else 80
    return p


def _base_template_context(request: Request) -> dict:
    return {"api_port": _infer_public_port(request)}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=_base_template_context(request),
    )


@router.get("/template", response_class=HTMLResponse)
async def template_gallery(request: Request):
    themes_ctx = []
    for tid in template_loader.theme_ids():
        tm = template_loader.theme_manifest(tid)
        slides = []
        for sk in template_loader.slide_kind_ids(tid):
            m = template_loader.manifest(tid, sk)
            slides.append(
                {
                    "manifest": m.model_dump(),
                    "html": template_loader.slide_html(tid, sk),
                    "slide_kind_id": sk,
                }
            )
        themes_ctx.append(
            {
                "theme": tm.model_dump(),
                "slides": slides,
            }
        )
    # 갤러리: 테마마다 별도 <style> 로 넣어 한 테마 CSS 파싱 오류가 다른 테마에 전파되지 않게 함
    gallery_theme_css = [
        {"theme_id": tid, "css": template_loader.all_css_for_gallery(tid)}
        for tid in template_loader.theme_ids()
    ]
    try:
        templates_dir_display = str(template_loader._dir.resolve())
    except OSError:
        templates_dir_display = str(template_loader._dir)

    ctx = _base_template_context(request)
    ctx.update(
        {
            "gallery_theme_css": gallery_theme_css,
            "themes": themes_ctx,
            "slide_templates_dir": templates_dir_display,
        }
    )
    return templates.TemplateResponse(
        request=request,
        name="template_gallery.html",
        context=ctx,
    )


@router.get("/preview/{deck_id}", response_class=HTMLResponse)
async def preview_deck(request: Request, deck_id: str):
    deck = deck_store.get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    all_css = template_loader.all_css(deck.theme_id)
    slides_html = [s.html for s in deck.slides]

    ctx = _base_template_context(request)
    ctx.update(
        {
            "deck_id": deck_id,
            "slides": slides_html,
            "all_css": all_css,
            "total": len(slides_html),
        }
    )
    return templates.TemplateResponse(
        request=request,
        name="preview.html",
        context=ctx,
    )

