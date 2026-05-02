import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.store import deck_store
from app.services.pdf_exporter import export_pdf
from app.services.pptx_exporter import export_pptx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/decks", tags=["export"])


def _get_deck_for_export(deck_id: str):
    deck = deck_store.get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    if not deck.slides:
        raise HTTPException(status_code=422, detail="Deck has no slides")
    return deck


def _slide_html_for_export(slide) -> str:
    export_html = getattr(slide, "export_html", None)
    return export_html or slide.html


def _slide_html_for_pdf(slide) -> str:
    return slide.html


@router.post("/{deck_id}/export/pdf")
async def export_deck_pdf(deck_id: str):
    deck = _get_deck_for_export(deck_id)
    slides_html = [_slide_html_for_pdf(s) for s in deck.slides]
    try:
        pdf_bytes = await export_pdf(slides_html, deck.theme_id)
    except Exception as e:
        logger.exception("PDF export 실패")
        raise HTTPException(status_code=500, detail=f"PDF 생성 실패: {e}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="portfolio.pdf"',
        },
    )


@router.post("/{deck_id}/export/pptx")
async def export_deck_pptx(deck_id: str):
    deck = _get_deck_for_export(deck_id)
    slides_html = [_slide_html_for_export(s) for s in deck.slides]
    try:
        pptx_bytes = await export_pptx(slides_html, deck.theme_id)
    except Exception as e:
        logger.exception("PPTX export 실패")
        raise HTTPException(status_code=500, detail=f"PPTX 생성 실패: {e}")

    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": 'attachment; filename="portfolio.pptx"',
        },
    )
