# 🌾 Bharat Farms

A plot-driven crop-intelligence platform for Indian farmers.

Lock a field on the map and Bharat Farms:

1. **Pulls its satellite history** — Sentinel-2 true-colour thumbnails + an NDVI
   time-series for the exact polygon, back to 2016 (Microsoft Planetary Computer,
   free, no signup).
2. **Infers the crops usually grown there** — from the NDVI seasonal pattern +
   regional cropping priors, sharpened by OpenAI when a key is set.
3. **Forecasts the upcoming market value** of those crops — trend + seasonality
   over Agmarknet mandi-price history.
4. **Tracks the live rate like a stock** — a ticker + watchlist of wholesale
   (mandi) modal prices with day-change and a 45-day sparkline, for the exact
   commodity the farmer grows.
5. **Surfaces daily regional news** — headlines for the plot's crops + state,
   labelled *good for you / watch out / neutral* for grower income (Google News
   RSS + OpenAI classification).

Plus voice in every major Indian language (OpenAI STT/TTS) and a photo-based
crop-health check (OpenAI vision).

> This is a full rewrite. The old Dwani.ai Flask scripts and the static mockups
> have been removed; everything now runs through one FastAPI service.

---

## Architecture

```
backend/     FastAPI (Python) — JSON API under /api/* + serves the frontend
  app/
    routers/    plots, analysis, prices, news, voice, weather, health, admin
    services/   openai_client, satellite, crop_history, prices, forecast,
                news_feed, geocode, region_priors, analysis_runner
    jobs/       daily_refresh  (prices + news; run by APScheduler or cron)
frontend/    Static HTML + Bootstrap + Leaflet + Chart.js (vanilla JS, no build)
render.yaml  One Render web service (disk-backed SQLite + in-process scheduler)
```

| Concern | Choice |
|---|---|
| Backend | FastAPI + SQLModel (SQLite) |
| Frontend | Static HTML / Bootstrap 5 / Leaflet + Leaflet-Geoman / Chart.js |
| Accounts | None — a browser `localStorage` device id keys plots & watchlist |
| Vision / STT / TTS | OpenAI API (`OPENAI_*` models, all configurable) |
| Plot imagery | Sentinel-2 L2A via Microsoft Planetary Computer (free) |
| Mandi prices | data.gov.in / Agmarknet resource `9ef84268-d588-465a-a308-a864a43d0070` |
| Reverse geocoding | BigDataCloud (no key) → Nominatim fallback |
| News | Google News RSS (no key) + OpenAI impact labelling |
| Weather | OpenWeather (current + 5-day) |

Every external dependency **degrades gracefully**: with no keys set the app still
maps plots, shows satellite history + NDVI, infers crops from regional priors,
and lists raw news — the AI/price/weather layers just stay empty and say why.

---

## Local setup

Python 3.11–3.13. **Use one interpreter consistently** — don't create the venv
with one `python` and run it with another (e.g. a system Python vs. a conda
`base`). The commands below call the venv's own executable by path to avoid that.

```bash
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt      # Windows
# .venv/bin/python -m pip install -r requirements.txt        # macOS / Linux

copy .env.example .env                                       # then edit .env  (cp on *nix)
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Open <http://127.0.0.1:8000>.

> **`ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`** means
> the venv's interpreter and its installed wheels are from different Python
> versions (usually a second `python -m venv .venv` run by a different `python`).
> Fix: `rmdir /s /q .venv` (or `rm -rf .venv`), then redo the steps above with
> a single interpreter.

### Keys (all optional, all free tiers)

| Env var | Get it from | Unlocks |
|---|---|---|
| `OPENAI_API_KEY` | <https://platform.openai.com/api-keys> | voice, photo diagnosis, AI crop inference, news impact labels |
| `DATA_GOV_IN_API_KEY` | <https://data.gov.in> → profile → *Generate API key* | live mandi prices, price forecast |
| `OPENWEATHER_API_KEY` | <https://openweathermap.org/api> | weather panel |

`OPENAI_VISION_MODEL`, `OPENAI_STT_MODEL`, `OPENAI_TTS_MODEL`, `OPENAI_TTS_VOICE`,
`OPENAI_CHAT_MODEL` are all overridable in `.env` as OpenAI's line-up changes.

### Daily refresh

```bash
python -m app.jobs.daily_refresh          # refresh prices + news for all plots/watchlists
```

Set `ENABLE_SCHEDULER=true` to run this automatically at 06:30 IST in-process,
or `POST /api/admin/refresh` (guard with `ADMIN_TOKEN`) to trigger it on demand.

---

## Deploy to Render

1. Push to GitHub, then **New → Blueprint** and point Render at `render.yaml`.
2. After the first deploy, set the secret env vars in the dashboard:
   `OPENAI_API_KEY`, `DATA_GOV_IN_API_KEY`, `OPENWEATHER_API_KEY`, `ADMIN_TOKEN`.
3. `render.yaml` provisions one web service with a 1 GB disk for SQLite at
   `/var/data` and runs the daily refresh in-process (`ENABLE_SCHEDULER=true`).

Free tier: drop the `disk:` block and point `DATABASE_URL` at a hosted Postgres
instead (the code is plain SQLModel/SQL). A dedicated Cron Job variant is included
commented-out in `render.yaml`.

---

## API surface

| Method & path | Purpose |
|---|---|
| `POST /api/plots` | create + lock a plot (GeoJSON polygon) → kicks off analysis |
| `GET /api/plots` · `GET /api/plots/{id}` · `DELETE /api/plots/{id}` | manage plots |
| `POST /api/plots/{id}/reanalyze` | re-run the analysis pipeline |
| `GET /api/plots/{id}/analysis` | satellite thumbnails, NDVI series, inferred crops, price outlook |
| `GET /api/prices?commodity=&state=` | latest mandi quote + day change |
| `GET /api/prices/{commodity}/history?state=&days=` | modal-price series |
| `GET/POST/DELETE /api/watchlist` | device-scoped watchlist |
| `GET /api/news?crop=&state=&impact=` · `POST /api/news/refresh` | regional news feed |
| `POST /api/voice/stt` · `POST /api/voice/tts` · `POST /api/voice/assistant` | voice (multilingual) |
| `POST /api/health/diagnose` | crop photo → diagnosis in chosen language |
| `GET /api/weather?lat=&lon=` | current + 5-day forecast |
| `GET /api/status` | which integrations are configured |

Interactive docs at `/docs`.
