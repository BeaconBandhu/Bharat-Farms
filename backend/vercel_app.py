"""Vercel entrypoint (vercel.json -> services.bharat-farms.entrypoint).

Sets serverless-appropriate defaults, then exposes the FastAPI `app`:
  * SQLite in /tmp - the only writable path. Ephemeral: plots / watchlist /
    news reset when the instance recycles. Set DATABASE_URL to a hosted
    Postgres in the Vercel project env to make data durable.
  * INLINE_ANALYSIS so the plot pipeline runs during the request rather than as
    a background task that would not survive the response.

Secret keys (OPENAI_API_KEY, OPENWEATHER_API_KEY, DATA_GOV_IN_API_KEY,
AGRO_API_KEY) come from the Vercel project environment.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/bharatfarms.db")
os.environ.setdefault("INLINE_ANALYSIS", "true")
os.environ.setdefault("ENABLE_SCHEDULER", "false")

from app.main import app  # noqa: E402,F401
