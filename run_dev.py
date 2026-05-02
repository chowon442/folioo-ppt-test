"""
Windows에서 `uvicorn --reload`만 쓰면 Playwright가 깨집니다(uvicorn이 Selector 루프 강제).
이 스크립트는 --loop none으로 띄워 Proactor(서브프로세스)를 유지합니다.

    python run_dev.py
    python run_dev.py --port 8010
"""
import argparse
import asyncio
import os
import socket
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8001")))
    parser.add_argument("--no-reload", action="store_true")
    return parser.parse_args()


def _can_bind(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
        return True
    except OSError:
        return False


def _pick_port(host: str, requested_port: int) -> int:
    candidates = [
        requested_port,
        8001,
        8010,
        8080,
        18080,
        3000,
        5000,
        5050,
        8501,
        8765,
    ]
    seen = set()
    for port in candidates:
        if port in seen:
            continue
        seen.add(port)
        if _can_bind(host, port):
            return port
    raise RuntimeError(
        f"{host} 에 바인딩 가능한 포트를 찾지 못했습니다. "
        "Windows 예약 포트일 수 있으니 `netsh interface ipv4 show excludedportrange protocol=tcp` 로 확인해보세요."
    )


if __name__ == "__main__":
    args = _parse_args()
    port = _pick_port(args.host, args.port)
    if port != args.port:
        print(
            f"[run_dev] requested port {args.port} is unavailable; using {port} instead.",
            file=sys.stderr,
        )
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=port,
        reload=not args.no_reload,
        loop="none",
    )
