"""FastAPI application entrypoint.

Serves the JSON API under /api/* and the static site from the `public/`
directory (bundled at backend/public; also found at the repo root for older
checkouts). One FastAPI app for local dev, Render and Vercel alike.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .routers import (
    admin,
    analysis,
    health,
    news,
    plots,
    prices,
    recommend,
    voice,
    weather,
)

settings = get_settings()
_here = Path(__file__).resolve()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if settings.enable_scheduler:
        from .scheduler import shutdown_scheduler, start_scheduler

        start_scheduler()
        try:
            yield
        finally:
            shutdown_scheduler()
    else:
        yield


app = FastAPI(title="Bharat Farms API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (plots, analysis, prices, news, voice, weather, health, recommend, admin):
    app.include_router(module.router)


@app.get("/api/status", tags=["meta"])
def status():
    return {
        "status": "ok",
        "openai": settings.openai_enabled,
        "prices": bool(settings.data_gov_in_api_key),
        "weather": bool(settings.openweather_api_key),
        "agro": bool(settings.agro_api_key),
    }


# Serve the static site from public/ (sits at backend/public). On Vercel the
# platform serves that directory straight from the CDN, so we must NOT also
# mount it (Vercel's docs are explicit about this); locally and on Render the
# mount does the serving.
if not os.environ.get("VERCEL"):
    _public = next(
        (p for p in (_here.parents[1] / "public", _here.parents[2] / "public") if p.is_dir()),
        None,
    )
    if _public is not None:
        app.mount("/", StaticFiles(directory=str(_public), html=True), name="site")
