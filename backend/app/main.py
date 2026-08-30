"""FastAPI application entrypoint.

Serves the JSON API under /api/* and the static site in ../../public.

On Vercel (`VERCEL` env set) the `public/` directory is served straight from
the CDN, so the StaticFiles mount is skipped and `/` just redirects to
`/index.html`. Locally and on Render the mount serves everything.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
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
ON_VERCEL = bool(os.environ.get("VERCEL"))
PUBLIC_DIR = Path(__file__).resolve().parents[2] / "public"


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


if ON_VERCEL:
    @app.get("/", include_in_schema=False)
    def _root():
        return RedirectResponse("/index.html", status_code=307)
elif PUBLIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="site")
