"""Ops endpoints (manual refresh trigger)."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from ..config import get_settings
from ..jobs.daily_refresh import main as daily_refresh_main

router = APIRouter(prefix="/api/admin", tags=["admin"])
_settings = get_settings()


@router.post("/refresh")
async def trigger_refresh(x_admin_token: str | None = Header(default=None)):
    if _settings.admin_token and x_admin_token != _settings.admin_token:
        raise HTTPException(401, "Bad or missing X-Admin-Token.")
    await daily_refresh_main()
    return {"status": "refresh complete"}
