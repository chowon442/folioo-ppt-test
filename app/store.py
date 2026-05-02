from __future__ import annotations

import time
import uuid
from collections import OrderedDict

from app.config import settings
from app.models.schemas import DeckData, SlideData


class DeckStore:
    def __init__(self):
        self._store: OrderedDict[str, DeckData] = OrderedDict()

    def create_deck(self, theme_id: str = "default") -> DeckData:
        self._evict()
        deck = DeckData(
            deck_id=str(uuid.uuid4()),
            slides=[],
            created_at=time.time(),
            theme_id=theme_id,
        )
        self._store[deck.deck_id] = deck
        return deck

    def get_deck(self, deck_id: str) -> DeckData | None:
        deck = self._store.get(deck_id)
        if deck and self._is_expired(deck):
            del self._store[deck_id]
            return None
        return deck

    def add_slide(self, deck_id: str, slide: SlideData):
        deck = self._store.get(deck_id)
        if deck:
            deck.slides.append(slide)

    def _is_expired(self, deck: DeckData) -> bool:
        return time.time() - deck.created_at > settings.store_ttl_seconds

    def _evict(self):
        now = time.time()
        expired = [
            k for k, v in self._store.items()
            if now - v.created_at > settings.store_ttl_seconds
        ]
        for k in expired:
            del self._store[k]

        while len(self._store) >= settings.store_max_items:
            self._store.popitem(last=False)


deck_store = DeckStore()
