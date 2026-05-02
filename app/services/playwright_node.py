from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app.config import settings


def _tmp_root() -> Path:
    override = os.environ.get("PLAYWRIGHT_TMP_ROOT", "").strip()
    if override:
        root = Path(override).expanduser()
    else:
        root = Path("/tmp") / "ppt-test-playwright"
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    return root


def _playwright_paths() -> tuple[Path, Path]:
    try:
        import playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "playwright 패키지가 설치되어 있지 않아 HTML 기반 export를 실행할 수 없습니다."
        ) from exc

    module_file = getattr(playwright, "__file__", None)
    if not module_file:
        spec = importlib.util.find_spec("playwright")
        module_file = spec.origin if spec is not None else None
    if not module_file:
        raise RuntimeError("Playwright package path could not be resolved")

    root = Path(module_file).resolve().parent
    node_name = "node.exe" if os.name == "nt" else "node"
    node_path = root / "driver" / node_name
    package_dir = root / "driver" / "package"
    if not node_path.is_file():
        raise RuntimeError(f"Playwright driver node executable not found: {node_path}")
    if not package_dir.is_dir():
        raise RuntimeError(f"Playwright driver package not found: {package_dir}")
    return node_path, package_dir


def _playwright_env() -> dict[str, str]:
    tmp_dir = _tmp_root()
    env = os.environ.copy()
    tmp_text = str(tmp_dir)
    env["TMPDIR"] = tmp_text
    env["TMP"] = tmp_text
    env["TEMP"] = tmp_text

    if os.name != "nt":
        home_path = Path(env.get("HOME") or str(Path.home())).expanduser()
        env["HOME"] = str(home_path)
        xdg_runtime = Path(env.get("XDG_RUNTIME_DIR") or "")
        if not xdg_runtime.exists() or not os.access(xdg_runtime, os.W_OK):
            env["XDG_RUNTIME_DIR"] = tmp_text
    return env


async def run_playwright_job(
    *,
    mode: str,
    html: str,
    capture_script: str | None = None,
    viewport: dict[str, int] | None = None,
    pdf_options: dict[str, Any] | None = None,
    browser_order: list[str] | None = None,
) -> bytes | dict[str, Any]:
    if mode not in {"snapshot", "pdf"}:
        raise ValueError(f"unsupported playwright job mode: {mode}")

    node_path, package_dir = _playwright_paths()
    runner_path = Path(__file__).with_name("playwright_runner.js")
    if not runner_path.is_file():
        raise RuntimeError(f"Playwright runner script not found: {runner_path}")

    payload = {
        "mode": mode,
        "html": html,
        "captureScript": capture_script,
        "viewport": viewport or {"width": 1280, "height": 720},
        "pdfOptions": pdf_options or {},
        "browserOrder": browser_order or (
            ["chromium"]
            if mode == "snapshot"
            else ["chromium"]
        ),
    }

    env = _playwright_env()
    env["PLAYWRIGHT_PACKAGE_DIR"] = str(package_dir)
    overall_timeout = float(env.get("PLAYWRIGHT_RUNNER_OVERALL_TIMEOUT_MS", "45000")) / 1000.0

    with tempfile.TemporaryDirectory(dir=str(_tmp_root())) as temp_dir:
        temp_root = Path(temp_dir)
        input_path = temp_root / "input.json"
        output_path = temp_root / ("output.json" if mode == "snapshot" else "output.bin")
        error_path = temp_root / "stderr.txt"
        input_path.write_text(json.dumps(payload), encoding="utf-8")

        proc = await asyncio.create_subprocess_exec(
            str(node_path),
            str(runner_path),
            str(input_path),
            str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=overall_timeout,
            )
        except asyncio.TimeoutError as exc:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.communicate()
            raise RuntimeError(
                f"Playwright runner timed out after {overall_timeout:.0f}s"
            ) from exc

        stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
        stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            detail = stderr_text or stdout_text or "unknown playwright runner error"
            raise RuntimeError(f"Playwright runner failed: {detail}")

        if not output_path.exists():
            raise RuntimeError("Playwright runner finished without producing output")

        if mode == "snapshot":
            return json.loads(output_path.read_text(encoding="utf-8"))
        return output_path.read_bytes()
