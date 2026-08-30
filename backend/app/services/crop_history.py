"""Infer the crops usually grown on a plot from its NDVI seasonal pattern.

Combines: (1) the region prior table, (2) OpenAI reasoning over the NDVI
time-series + a few satellite thumbnails. Region priors are always returned
so the feature still works with no OpenAI key / no imagery.
"""
from __future__ import annotations

import json

from ..config import get_settings
from . import openai_client, region_priors

_settings = get_settings()


def _season_summary(ndvi_series: list[dict]) -> str:
    if not ndvi_series:
        return "No NDVI data available."
    by_month: dict[int, list[float]] = {}
    for row in ndvi_series:
        try:
            month = int(row["date"][5:7])
        except (KeyError, ValueError):
            continue
        by_month.setdefault(month, []).append(float(row["ndvi"]))
    if not by_month:
        return "No NDVI data available."
    parts = []
    for m in range(1, 13):
        if m in by_month:
            avg = sum(by_month[m]) / len(by_month[m])
            parts.append(f"{m:02d}:{avg:.2f}")
    return "monthly mean NDVI -> " + ", ".join(parts)


def infer_crops(
    *,
    state: str | None,
    district: str | None,
    area_hectares: float,
    ndvi_series: list[dict],
    thumbnails: list[dict],
) -> dict:
    priors = region_priors.priors_for_state(state)
    prior_list = region_priors.likely_crops(state)

    fallback = {
        "inferred_crops": [
            {
                "crop": c,
                "confidence": "low",
                "seasons": _seasons_for(c, priors),
                "reason": "Typical for this state (regional prior).",
            }
            for c in prior_list[:6]
        ],
        "summary_text": (
            f"Based on regional cropping patterns for {state or 'India'}, this plot is "
            f"most likely used for: {', '.join(prior_list[:6])}."
        ),
        "ai_model": "",
    }

    if not _settings.openai_enabled:
        return fallback

    season_line = _season_summary(ndvi_series)
    system = (
        "You are an agronomist reading a farm plot's multi-year Sentinel-2 NDVI "
        "history to identify which crops are usually grown there. Reply ONLY with JSON."
    )
    prompt = (
        f"Location: state={state or 'unknown'}, district={district or 'unknown'}, "
        f"plot area={area_hectares:.2f} ha.\n"
        f"Regional common crops: {', '.join(prior_list)}.\n"
        f"NDVI time-series ({len(ndvi_series)} points): {season_line}\n"
        "Green-up in Jun-Oct suggests Kharif crops; Nov-Mar suggests Rabi; "
        "year-round high NDVI suggests plantation/perennial or sugarcane.\n\n"
        'Return JSON: {"crops":[{"crop":"Rice","confidence":"high|medium|low",'
        '"seasons":["Kharif"],"reason":"<=20 words"}],"summary":"2-3 sentence plain summary"}'
        "\nList 2-5 crops, most likely first."
    )
    images: list[tuple[bytes, str]] = []  # thumbnails are remote URLs; keep prompt text-only
    try:
        data = openai_client.chat_json(prompt, system=system, images=images or None)
    except openai_client.OpenAIUnavailable:
        return fallback

    crops = data.get("crops") if isinstance(data, dict) else None
    if not crops:
        return fallback

    cleaned = []
    for row in crops[:5]:
        if not isinstance(row, dict) or not row.get("crop"):
            continue
        conf = str(row.get("confidence", "low")).lower()
        cleaned.append(
            {
                "crop": str(row["crop"]).strip().title(),
                "confidence": conf if conf in {"high", "medium", "low"} else "low",
                "seasons": [str(s).title() for s in (row.get("seasons") or [])][:3],
                "reason": str(row.get("reason", ""))[:200],
            }
        )
    if not cleaned:
        return fallback

    return {
        "inferred_crops": cleaned,
        "summary_text": str(data.get("summary", fallback["summary_text"]))[:800],
        "ai_model": _settings.openai_vision_model,
    }


def _seasons_for(crop: str, priors: dict[str, list[str]]) -> list[str]:
    out = []
    for season in ("kharif", "rabi"):
        if crop in priors.get(season, []):
            out.append(season.title())
    return out or ["Unknown"]
