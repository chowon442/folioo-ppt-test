from __future__ import annotations

import asyncio
import os
from pathlib import Path

from app.services.pptx_exporter import _ensure_theme_template_pptx
from app.services.template_loader import template_loader


async def main() -> None:
    os.environ.setdefault("PLAYWRIGHT_RUNNER_OVERALL_TIMEOUT_MS", "180000")
    os.environ.setdefault("PLAYWRIGHT_RUNNER_TIMEOUT_MS", "60000")

    theme_ids = template_loader.theme_ids()
    if not theme_ids:
        raise SystemExit("no themes found")

    for theme_id in theme_ids:
        output = await _ensure_theme_template_pptx(theme_id)
        if not output:
            raise SystemExit(f"failed to build PPTX template for theme={theme_id}")
        print(f"{theme_id}: {Path(output)}")


if __name__ == "__main__":
    asyncio.run(main())
