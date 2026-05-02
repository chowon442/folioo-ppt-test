from __future__ import annotations

import time
import uuid
from collections import OrderedDict

from app.config import settings
from app.models.schemas import GenerationPlanRecord, PagePlanItem


class PlanStore:
    """생성 계획(plan_id)을 TTL로 보관한다."""

    def __init__(self):
        self._store: OrderedDict[str, GenerationPlanRecord] = OrderedDict()

    def create_plan(
        self,
        outline: str,
        pages: list[PagePlanItem],
        theme_id: str,
        source_text: str,
    ) -> GenerationPlanRecord:
        self._evict()
        rec = GenerationPlanRecord(
            plan_id=str(uuid.uuid4()),
            outline=outline,
            pages=pages,
            theme_id=theme_id,
            source_text=source_text,
            created_at=time.time(),
        )
        self._store[rec.plan_id] = rec
        return rec

    def get_plan(self, plan_id: str) -> GenerationPlanRecord | None:
        rec = self._store.get(plan_id)
        if rec is None:
            return None
        if self._is_expired(rec):
            del self._store[plan_id]
            return None
        return rec

    def _is_expired(self, rec: GenerationPlanRecord) -> bool:
        return time.time() - rec.created_at > settings.store_ttl_seconds

    def _evict(self):
        now = time.time()
        expired = [
            k
            for k, v in self._store.items()
            if now - v.created_at > settings.store_ttl_seconds
        ]
        for k in expired:
            del self._store[k]

        while len(self._store) >= settings.store_max_items:
            self._store.popitem(last=False)


plan_store = PlanStore()
