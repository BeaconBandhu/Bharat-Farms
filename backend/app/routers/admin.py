"""Ops endpoints (manual / cron refresh trigger)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException

from ..config import get_settings
from ..jobs.daily_refresh import main as daily_refresh_main

router = APIRouter(prefix="/api/admin", tags=["admin"])
_settings = get_settings()


def _authorized(x_admin_token: str | None, authorization: str | None) -> bool:
    # Vercel Cron sends `Authorization: Bearer <CRON_SECRET>`.
    cron_secret = os.environ.get("CRON_SECRET", "")
    if cron_secret and authorization == f"Bearer {cron_secret}":
        return True
    if _settings.admin_token:
        return x_admin_token == _settings.admin_token
    # No secret configured at all -> allow (fine for a demo deploy).
    return not cron_secret


async def _run() -> dict:
    await daily_refresh_main()
    return {"status": "refresh complete"}


@router.get("/refresh")
async def trigger_refresh_get(
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    if not _authorized(x_admin_token, authorization):
        raise HTTPException(401, "Unauthorized.")
    return await _run()


@router.post("/refresh")
async def trigger_refresh_post(
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    if not _authorized(x_admin_token, authorization):
        raise HTTPException(401, "Unauthorized.")
    return await _run()
