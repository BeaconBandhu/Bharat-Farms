"""Naive price outlook: linear trend + month-of-year seasonal offset.

Deliberately simple and transparent - this is decision support, not a
trading model. Confidence is reported honestly based on how much history
we actually have.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np


def _to_arrays(points: list[dict]) -> tuple[np.ndarray, np.ndarray, list[date]]:
    pts = sorted(
        (p for p in points if p.get("modal_price") is not None),
        key=lambda p: p["arrival_date"],
    )
    dates = [p["arrival_date"] for p in pts]
    if not dates:
        return np.array([]), np.array([]), []
    base = dates[0]
    x = np.array([(d - base).days for d in dates], dtype=float)
    y = np.array([float(p["modal_price"]) for p in pts], dtype=float)
    return x, y, dates


def forecast_price(points: list[dict], horizon_weeks: int = 6) -> dict:
    x, y, dates = _to_arrays(points)
    n = len(y)

    if n < 4:
        current = float(y[-1]) if n else None
        return {
            "method": "insufficient-data",
            "confidence": "low",
            "current": current,
            "projected_mid": current,
            "projected_low": current,
            "projected_high": current,
            "direction": "unknown",
            "change_pct": None,
            "horizon_weeks": horizon_weeks,
            "points": n,
        }

    # Linear trend.
    slope, intercept = np.polyfit(x, y, 1)
    trend = slope * x + intercept
    resid = y - trend

    # Month-of-year seasonal offset (mean residual per calendar month).
    month_offset: dict[int, float] = {}
    for d, r in zip(dates, resid):
        month_offset.setdefault(d.month, []).append(r)
    month_offset = {m: float(np.mean(v)) for m, v in month_offset.items()}

    horizon_days = horizon_weeks * 7
    target_date = dates[-1] + timedelta(days=horizon_days)
    x_future = (target_date - dates[0]).days
    base_pred = slope * x_future + intercept + month_offset.get(target_date.month, 0.0)

    sigma = float(np.std(resid)) or max(1.0, 0.02 * float(y[-1]))
    current = float(y[-1])
    projected_mid = float(base_pred)
    change_pct = round((projected_mid - current) / current * 100, 1) if current else None

    if change_pct is None:
        direction = "unknown"
    elif change_pct >= 3:
        direction = "up"
    elif change_pct <= -3:
        direction = "down"
    else:
        direction = "flat"

    span_days = (dates[-1] - dates[0]).days
    if n >= 12 and span_days >= 60:
        confidence = "medium"
    elif n >= 20 and span_days >= 120:
        confidence = "high"
    else:
        confidence = "low"

    return {
        "method": "linear-trend+seasonal",
        "confidence": confidence,
        "current": round(current, 2),
        "projected_mid": round(projected_mid, 2),
        "projected_low": round(projected_mid - 1.5 * sigma, 2),
        "projected_high": round(projected_mid + 1.5 * sigma, 2),
        "direction": direction,
        "change_pct": change_pct,
        "horizon_weeks": horizon_weeks,
        "target_date": target_date.isoformat(),
        "points": n,
    }
