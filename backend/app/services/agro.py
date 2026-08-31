"""Agromonitoring (agromonitoring.com) — per-polygon NDVI stats, soil and
accumulated weather. All calls are best-effort and never raise; callers treat
a None / empty result as "feature not configured or unavailable".

Free plan limits: 1 polygon call/sec, ~1000 ha of polygons total, 1-3000 ha
per polygon. Needs its own AGRO_API_KEY (an OpenWeather key is rejected).
"""
from __future__ import annotations

import time

import httpx

from ..config import get_settings

_settings = get_settings()
BASE = "http://api.agromonitoring.com/agro/1.0"
_TIMEOUT = 30
_KELVIN = 273.15


def enabled() -> bool:
    return bool(_settings.agro_key)


def _key() -> str:
    return _settings.agro_key


def ensure_polygon(name: str, geojson_feature: dict, area_hectares: float) -> str | None:
    """Create an Agromonitoring polygon; return its id (or None)."""
    if not enabled():
        return None
    if area_hectares < 1 or area_hectares > 3000:
        return None  # outside Agromonitoring's per-polygon limits
    geom = geojson_feature
    if geom.get("type") != "Feature":
        geom = {"type": "Feature", "properties": {}, "geometry": geojson_feature.get("geometry", geojson_feature)}
    try:
        resp = httpx.post(
            f"{BASE}/polygons",
            params={"appid": _key()},
            json={"name": name[:60] or "plot", "geo_json": geom},
            timeout=_TIMEOUT,
        )
        if resp.status_code in (200, 201):
            return resp.json().get("id")
    except httpx.HTTPError:
        pass
    return None


def delete_polygon(polygon_id: str) -> None:
    if not (enabled() and polygon_id):
        return
    try:
        httpx.delete(f"{BASE}/polygons/{polygon_id}", params={"appid": _key()}, timeout=_TIMEOUT)
    except httpx.HTTPError:
        pass


def ndvi_history(polygon_id: str, days: int = 730) -> list[dict]:
    """[{date, ndvi}] mean NDVI per satellite pass."""
    if not (enabled() and polygon_id):
        return []
    end = int(time.time())
    start = end - days * 86400
    try:
        resp = httpx.get(
            f"{BASE}/ndvi/history",
            params={"polyid": polygon_id, "start": start, "end": end, "appid": _key()},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        rows = resp.json()
    except (httpx.HTTPError, ValueError):
        return []
    out: list[dict] = []
    for r in rows:
        data = r.get("data") or {}
        mean = data.get("mean")
        if mean is None or not r.get("dt"):
            continue
        out.append(
            {
                "date": time.strftime("%Y-%m-%d", time.gmtime(r["dt"])),
                "ndvi": round(float(mean), 3),
            }
        )
    out.sort(key=lambda x: x["date"])
    return out


def soil(polygon_id: str) -> dict | None:
    if not (enabled() and polygon_id):
        return None
    try:
        resp = httpx.get(f"{BASE}/soil", params={"polyid": polygon_id, "appid": _key()}, timeout=_TIMEOUT)
        resp.raise_for_status()
        d = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    if "moisture" not in d:
        return None
    return {
        "moisture_m3_m3": round(d.get("moisture", 0), 3),
        "surface_temp_c": round(d.get("t0", _KELVIN) - _KELVIN, 1),
        "temp_10cm_c": round(d.get("t10", _KELVIN) - _KELVIN, 1),
        "as_of": time.strftime("%Y-%m-%d", time.gmtime(d.get("dt", time.time()))),
    }


def accumulated(polygon_id: str, days: int = 120) -> dict | None:
    """Accumulated rainfall (mm) and growing-degree-days (base 10 °C)."""
    if not (enabled() and polygon_id):
        return None
    end = int(time.time())
    start = end - days * 86400
    out: dict = {"days": days}
    try:
        rp = httpx.get(
            f"{BASE}/weather/history/accumulated_precipitation",
            params={"polyid": polygon_id, "start": start, "end": end, "appid": _key()},
            timeout=_TIMEOUT,
        )
        if rp.status_code == 200:
            out["rain_mm"] = round(sum(row.get("rain", 0) for row in rp.json()), 1)
    except (httpx.HTTPError, ValueError):
        pass
    try:
        rt = httpx.get(
            f"{BASE}/weather/history/accumulated_temperature",
            params={
                "polyid": polygon_id,
                "start": start,
                "end": end,
                "threshold": _KELVIN + 10,  # GDD base 10 °C
                "appid": _key(),
            },
            timeout=_TIMEOUT,
        )
        if rt.status_code == 200:
            out["gdd_base10_c"] = round(sum(row.get("temp", 0) for row in rt.json()), 0)
    except (httpx.HTTPError, ValueError):
        pass
    return out if len(out) > 1 else None
