"""Reverse geocoding: BigDataCloud (no key, datacenter-friendly) with an
OpenStreetMap Nominatim fallback.
"""
from __future__ import annotations

import httpx

from ..config import get_settings

_settings = get_settings()
_CACHE: dict[tuple[float, float], dict] = {}

BIGDATACLOUD_URL = "https://api.bigdatacloud.net/data/reverse-geocode-client"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


async def _try_bigdatacloud(client: httpx.AsyncClient, lat: float, lon: float) -> dict | None:
    resp = await client.get(
        BIGDATACLOUD_URL,
        params={"latitude": lat, "longitude": lon, "localityLanguage": "en"},
    )
    resp.raise_for_status()
    data = resp.json()
    if (data.get("countryCode") or "").upper() not in {"IN", ""} and not data.get(
        "principalSubdivision"
    ):
        return None
    district = data.get("city") or data.get("locality")
    if not district:
        for adm in reversed(data.get("localityInfo", {}).get("administrative", [])):
            if adm.get("adminLevel") in (5, 6) and adm.get("name"):
                district = adm["name"]
                break
    return {
        "state": data.get("principalSubdivision") or None,
        "district": district or None,
        "display_name": ", ".join(
            p for p in (district, data.get("principalSubdivision"), data.get("countryName")) if p
        ),
    }


async def _try_nominatim(client: httpx.AsyncClient, lat: float, lon: float) -> dict | None:
    resp = await client.get(
        NOMINATIM_URL,
        params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "addressdetails": 1},
        headers={"User-Agent": _settings.nominatim_user_agent, "Accept-Language": "en"},
    )
    resp.raise_for_status()
    data = resp.json()
    addr = data.get("address", {})
    return {
        "state": addr.get("state") or addr.get("region"),
        "district": (
            addr.get("state_district")
            or addr.get("county")
            or addr.get("district")
            or addr.get("city")
        ),
        "display_name": data.get("display_name"),
    }


async def reverse_geocode(lat: float, lon: float) -> dict:
    """Best-effort {state, district, display_name}. Never raises."""
    key = (round(lat, 3), round(lon, 3))
    if key in _CACHE:
        return _CACHE[key]

    result: dict = {"state": None, "district": None, "display_name": None}
    async with httpx.AsyncClient(timeout=_settings.request_timeout_seconds) as client:
        for provider in (_try_bigdatacloud, _try_nominatim):
            try:
                got = await provider(client, lat, lon)
            except Exception as exc:  # noqa: BLE001 - try the next provider
                result["error"] = str(exc)
                continue
            if got and got.get("state"):
                result = got
                break

    _CACHE[key] = result
    return result
