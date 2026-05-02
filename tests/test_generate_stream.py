from __future__ import annotations

import json
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

if "fastapi" not in sys.modules:
    fastapi_stub = types.ModuleType("fastapi")

    class _HTTPException(Exception):
        def __init__(self, status_code: int, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class _Response:
        def __init__(self, content=None, media_type=None, headers=None, **kwargs):
            self.content = content
            self.media_type = media_type
            self.headers = headers or {}
            self.kwargs = kwargs

    class _APIRouter:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def post(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

    fastapi_stub.APIRouter = _APIRouter
    fastapi_stub.HTTPException = _HTTPException
    fastapi_stub.Response = _Response
    sys.modules["fastapi"] = fastapi_stub

if "sse_starlette.sse" not in sys.modules:
    sse_pkg = types.ModuleType("sse_starlette")
    sse_mod = types.ModuleType("sse_starlette.sse")

    class _EventSourceResponse:
        def __init__(self, content):
            self.content = content

    sse_mod.EventSourceResponse = _EventSourceResponse
    sys.modules["sse_starlette"] = sse_pkg
    sys.modules["sse_starlette.sse"] = sse_mod

if "lxml" not in sys.modules:
    lxml_pkg = types.ModuleType("lxml")
    lxml_html_mod = types.ModuleType("lxml.html")
    lxml_etree_mod = types.ModuleType("lxml.etree")

    def _unavailable(*_args, **_kwargs):
        raise RuntimeError("lxml stub is only for import-time isolation")

    lxml_html_mod.fromstring = _unavailable
    lxml_html_mod.fragment_fromstring = _unavailable
    lxml_html_mod.tostring = _unavailable
    lxml_etree_mod.Element = _unavailable
    lxml_pkg.html = lxml_html_mod
    lxml_pkg.etree = lxml_etree_mod
    sys.modules["lxml"] = lxml_pkg
    sys.modules["lxml.html"] = lxml_html_mod
    sys.modules["lxml.etree"] = lxml_etree_mod

import app.routers.generate as generate_module
from app.models.schemas import PagePlanItem


class _ValidationResult:
    def __init__(self, valid: bool = True, errors: list[str] | None = None):
        self.valid = valid
        self.errors = list(errors or [])

    def add_error(self, error: str) -> None:
        self.valid = False
        self.errors.append(error)


class GenerateStreamRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_disconnect_recovers_remaining_slides_individually(self):
        pages = [
            PagePlanItem(
                index=1,
                template="cover",
                title="Intro",
                purpose="Introduce the portfolio",
                key_points=["one"],
            ),
            PagePlanItem(
                index=2,
                template="closing",
                title="Outro",
                purpose="Wrap up",
                key_points=["two"],
            ),
        ]

        async def broken_stream(_text: str, _theme_id: str, _pages: list[PagePlanItem]):
            yield {
                "id": 1,
                "template": "cover",
                "html": '<section class="slide sh-slide" data-template="cover"></section>',
            }
            raise RuntimeError("peer closed connection without sending complete message body")

        recovered_html = (
            '<section class="slide sh-slide" data-template="closing"></section>'
        )

        events: list[dict] = []
        with patch(
            "app.routers.generate.template_loader.all_manifests",
            return_value={"cover": object(), "closing": object()},
        ), patch(
            "app.routers.generate.normalize_slide_html",
            side_effect=lambda html, *_args: f"<normalized>{html}</normalized>",
        ), patch(
            "app.routers.generate.validate_slide_html",
            side_effect=lambda *_args, **_kwargs: _ValidationResult(),
        ), patch.object(
            generate_module.llm_service,
            "stream_generate_deck",
            new=broken_stream,
        ), patch.object(
            generate_module.llm_service,
            "generate_slide_from_plan",
            new=AsyncMock(return_value=recovered_html),
        ):
            async for event in generate_module._generate_stream(
                "portfolio", "default", pages
            ):
                events.append(event)

        event_names = [event["event"] for event in events]
        self.assertEqual(event_names[0], "generation_started")
        self.assertEqual(event_names.count("slide_ready"), 2)
        self.assertIn("deck_complete", event_names)
        self.assertNotIn("error", event_names)

        ready_payloads = [
            json.loads(event["data"])
            for event in events
            if event["event"] == "slide_ready"
        ]
        self.assertEqual(
            [payload["template"] for payload in ready_payloads],
            ["cover", "closing"],
        )
        self.assertEqual(
            [payload["html"] for payload in ready_payloads],
            [
                '<section class="slide sh-slide" data-template="cover"></section>',
                '<section class="slide sh-slide" data-template="closing"></section>',
            ],
        )

        deck_id = json.loads(events[0]["data"])["deck_id"]
        deck = generate_module.deck_store.get_deck(deck_id)
        self.assertIsNotNone(deck)
        assert deck is not None
        self.assertEqual([slide.html for slide in deck.slides], [payload["html"] for payload in ready_payloads])
        self.assertEqual(
            [slide.export_html for slide in deck.slides],
            [
                '<normalized><section class="slide sh-slide" data-template="cover"></section></normalized>',
                '<normalized><section class="slide sh-slide" data-template="closing"></section></normalized>',
            ],
        )


if __name__ == "__main__":
    unittest.main()
