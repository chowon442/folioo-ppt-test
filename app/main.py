import asyncio
import logging
import sys
from contextlib import asynccontextmanager

# Windows: Playwright는 subprocess가 필요함. uvicorn이 --reload 시
# WindowsSelectorEventLoopPolicy를 켜면 asyncio.create_subprocess_exec가
# NotImplementedError가 되므로, 개발 시 CLI는 --loop none 이거나 run_dev.py 사용.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.routers import generate, preview, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Slide Generator Demo",
    version="0.2.0",
    lifespan=lifespan,
    description="최신 빌드: paths에 /api/themes·/api/plan·/api/slide-kinds/{theme_id} 필요. GenerateRequest는 plan_id만 허용(text만 있으면 구버전 서버).",
)

# 다른 포트(예: Live Server)에서 정적만 열 때 /api/* 를 uvicorn(8000)으로 붙이기 위한 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(generate.router)
app.include_router(preview.router)
app.include_router(export.router)
