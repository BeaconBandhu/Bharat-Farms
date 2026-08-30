"""Current weather + short forecast (OpenWeather)."""
from __future__ import annotations

from collections import defaultdict

import httpx
from fastapi import APIRouter, HTTPException, Query

from ..config import get_settings

router = APIRouter(prefix="/api/weather", tags=["weather"])
_settings = get_settings()

CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


@router.get("")
async def weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    if not _settings.openweather_api_key:
        raise HTTPException(503, "OPENWEATHER_API_KEY is not configured.")

    params = {
        "lat": lat,
        "lon": lon,
        "appid": _settings.openweather_api_key,
        "units": "metric",
    }
    try:
        async with httpx.AsyncClient(timeout=_settings.request_timeout_seconds) as client:
            cur_resp, fc_resp = await client.get(CURRENT_URL, params=params), await client.get(
                FORECAST_URL, params=params
            )
        cur_resp.raise_for_status()
        fc_resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Weather provider error: {exc}") from exc

    cur = cur_resp.json()
    fc = fc_resp.json()

    daily: dict[str, dict] = defaultdict(
        lambda: {"temp_min": 99.0, "temp_max": -99.0, "conditions": defaultdict(int)}
    )
    for slot in fc.get("list", []):
        day = slot.get("dt_txt", " ").split(" ")[0]
        if not day:
            continue
        main = slot.get("main", {})
        daily[day]["temp_min"] = min(daily[day]["temp_min"], main.get("temp_min", 99))
        daily[day]["temp_max"] = max(daily[day]["temp_max"], main.get("temp_max", -99))
        wx = (slot.get("weather") or [{}])[0].get("main", "")
        if wx:
            daily[day]["conditions"][wx] += 1

    forecast = []
    for day, agg in list(daily.items())[:6]:
        condition = (
            max(agg["conditions"], key=agg["conditions"].get)
            if agg["conditions"]
            else "—"
        )
        forecast.append(
            {
                "date": day,
                "temp_min": round(agg["temp_min"], 1),
                "temp_max": round(agg["temp_max"], 1),
                "condition": condition,
            }
        )

    return {
        "location": cur.get("name") or f"{lat:.3f}, {lon:.3f}",
        "current": {
            "temp": round(cur.get("main", {}).get("temp", 0), 1),
            "feels_like": round(cur.get("main", {}).get("feels_like", 0), 1),
            "humidity": cur.get("main", {}).get("humidity"),
            "wind_speed": cur.get("wind", {}).get("speed"),
            "condition": (cur.get("weather") or [{}])[0].get("description", "").title(),
        },
        "forecast": forecast,
    }
