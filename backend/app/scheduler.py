"""Optional in-process daily scheduler for local development.

Enabled with ENABLE_SCHEDULER=true. The Render deployment uses a native
Cron Job (see render.yaml) instead, so this stays off in production.
"""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .jobs.daily_refresh import main as daily_refresh_main

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    _scheduler.add_job(
        daily_refresh_main,
        CronTrigger(hour=6, minute=30),
        id="daily_refresh",
        misfire_grace_time=3600,
        coalesce=True,
    )
    _scheduler.start()


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
