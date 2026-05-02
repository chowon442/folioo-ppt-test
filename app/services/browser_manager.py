from __future__ import annotations

import asyncio

from app.config import settings


class BrowserManager:
    """Compatibility shim for the old browser lifecycle API.

    HTML-based export no longer keeps a persistent Python Playwright browser open.
    Snapshot/PDF rendering is delegated to the Node Playwright runner on demand.
    """

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.browser_concurrency)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def new_context(self):
        raise RuntimeError(
            "Persistent browser contexts are no longer supported. "
            "Use the Node Playwright runner helpers instead."
        )

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._semaphore


browser_manager = BrowserManager()
