"""Historical Sentinel-2 imagery for a plot, via Microsoft Planetary Computer.

Free, no signup. STAC search is well-documented and stable; the raster/
tiler endpoints are best-effort (any failure just yields fewer data points,
never an exception that breaks plot analysis).
"""
from __future__ import annotations

import io
from datetime import date, datetime, timedelta, timezone

import httpx
import numpy as np

STAC_API = "https://planetarycomputer.microsoft.com/api/stac/v1"
DATA_API = "https://planetarycomputer.microsoft.com/api/data/v1"
COLLECTION = "sentinel-2-l2a"

_HTTP_TIMEOUT = 40


def _search_items(bbox: list[float], geometry: dict, years: int, max_items: int) -> list[dict]:
    """STAC search, ~one lowest-cloud scene per 2-month bucket."""
    try:
        from pystac_client import Client
    except ImportError:  # pragma: no cover
        return []

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * years)
    try:
        client = Client.open(STAC_API)
        search = client.search(
            collections=[COLLECTION],
            bbox=bbox,
            datetime=f"{start.date()}/{end.date()}",
            query={"eo:cloud_cover": {"lt": 25}},
            sortby=[{"field": "properties.datetime", "direction": "asc"}],
            max_items=600,
        )
        items = [it.to_dict() for it in search.items()]
    except Exception:  # noqa: BLE001
        return []

    buckets: dict[str, dict] = {}
    for it in items:
        props = it.get("properties", {})
        dt = props.get("datetime", "")[:10]
        if not dt:
            continue
        d = date.fromisoformat(dt)
        key = f"{d.year}-{(d.month - 1) // 2}"
        cloud = props.get("eo:cloud_cover", 100)
        if key not in buckets or cloud < buckets[key]["properties"].get("eo:cloud_cover", 100):
            buckets[key] = it

    chosen = sorted(buckets.values(), key=lambda it: it["properties"]["datetime"])
    if len(chosen) > max_items:
        step = len(chosen) / max_items
        chosen = [chosen[int(i * step)] for i in range(max_items)]
    return chosen


def _bbox_str(bbox: list[float]) -> str:
    return ",".join(f"{c:.6f}" for c in bbox)


def _thumb_url(item: dict, bbox: list[float]) -> str:
    """True-colour PNG clipped to the plot bbox (Planetary Computer tiler)."""
    item_id = item.get("id", "")
    return (
        f"{DATA_API}/item/bbox/{_bbox_str(bbox)}.png"
        f"?collection={COLLECTION}&item={item_id}"
        f"&assets=visual&asset_bidx=visual|1,2,3&nodata=0&max_size=480"
    )


def _mean_ndvi(item: dict, bbox: list[float]) -> float | None:
    """Fetch a tiny B04/B08 array as .npy and return mean NDVI over the plot bbox."""
    item_id = item.get("id", "")
    url = (
        f"{DATA_API}/item/bbox/{_bbox_str(bbox)}.npy"
        f"?collection={COLLECTION}&item={item_id}"
        f"&assets=B04&assets=B08&max_size=64"
    )
    try:
        resp = httpx.get(url, timeout=_HTTP_TIMEOUT)
        resp.raise_for_status()
        arr = np.load(io.BytesIO(resp.content), allow_pickle=False)
    except Exception:  # noqa: BLE001
        return None

    # titiler .npy -> (bands[, mask], h, w); first two bands are B04, B08.
    if arr.ndim != 3 or arr.shape[0] < 2:
        return None
    red = arr[0].astype("float32")
    nir = arr[1].astype("float32")
    if arr.shape[0] >= 3:  # last band is an alpha/mask
        mask = arr[-1].astype(bool)
        red[~mask] = np.nan
        nir[~mask] = np.nan

    denom = nir + red
    denom[denom == 0] = np.nan
    ndvi = (nir - red) / denom
    ndvi = ndvi[np.isfinite(ndvi)]
    if ndvi.size == 0:
        return None
    return round(float(np.mean(ndvi)), 3)


def plot_imagery(
    geometry: dict,
    bbox: list[float],
    *,
    years: int = 5,
    max_items: int = 16,
) -> dict:
    """Return {thumbnails: [{date,url}], ndvi_series: [{date,ndvi}], note}."""
    items = _search_items(bbox, geometry, years, max_items)
    if not items:
        return {
            "thumbnails": [],
            "ndvi_series": [],
            "note": "No cloud-free Sentinel-2 scenes found for this plot.",
        }

    thumbnails: list[dict] = []
    ndvi_series: list[dict] = []
    for it in items:
        day = it["properties"]["datetime"][:10]
        thumbnails.append({"date": day, "url": _thumb_url(it, bbox)})
        ndvi = _mean_ndvi(it, bbox)
        if ndvi is not None:
            ndvi_series.append({"date": day, "ndvi": ndvi})

    note = ""
    if not ndvi_series:
        note = "Imagery found, but NDVI values could not be computed."
    return {"thumbnails": thumbnails, "ndvi_series": ndvi_series, "note": note}
