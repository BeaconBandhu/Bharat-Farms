"""Orchestrates the locked-plot analysis pipeline.

satellite imagery -> crop-history inference -> per-crop price outlook.
Run as a FastAPI background task (async); blocking work is pushed to the
threadpool so it never stalls the event loop.
"""
from __future__ import annotations

from datetime import date, datetime

from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session, select

from ..db import engine
from ..models import Plot, PlotAnalysis, utcnow
from . import crop_history, forecast, prices, satellite
from .geometry import padded_bbox, polygon_stats


def _json_safe(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def get_or_create_analysis(session: Session, plot_id: int) -> PlotAnalysis:
    analysis = session.exec(
        select(PlotAnalysis).where(PlotAnalysis.plot_id == plot_id)
    ).first()
    if analysis is None:
        analysis = PlotAnalysis(plot_id=plot_id, status="pending")
        session.add(analysis)
        session.commit()
        session.refresh(analysis)
    return analysis


async def run_analysis(plot_id: int) -> None:
    with Session(engine) as session:
        plot = session.get(Plot, plot_id)
        if plot is None:
            return
        analysis = get_or_create_analysis(session, plot_id)
        analysis.status = "running"
        analysis.error = ""
        analysis.updated_at = utcnow()
        session.add(analysis)
        session.commit()

        try:
            stats = polygon_stats(plot.geojson)
            bbox = padded_bbox(stats["bbox"])
            geometry = stats["geometry"]

            imagery = await run_in_threadpool(
                satellite.plot_imagery, geometry, bbox
            )

            crop_info = await run_in_threadpool(
                crop_history.infer_crops,
                state=plot.state,
                district=plot.district,
                area_hectares=plot.area_hectares,
                ndvi_series=imagery["ndvi_series"],
                thumbnails=imagery["thumbnails"],
            )

            outlook: list[dict] = []
            for entry in crop_info["inferred_crops"]:
                crop = entry["crop"]
                try:
                    await prices.ensure_fresh(session, crop, plot.state)
                except Exception:  # noqa: BLE001
                    pass
                history = prices.get_history(session, crop, plot.state, days=150)
                quote = prices.get_quote(session, crop, plot.state)
                outlook.append(
                    {
                        "crop": crop,
                        "confidence": entry.get("confidence"),
                        "quote": _json_safe(quote) if quote else None,
                        "forecast": forecast.forecast_price(history),
                        "history_points": len(history),
                    }
                )

            analysis.thumbnails = _json_safe(imagery["thumbnails"])
            analysis.ndvi_series = _json_safe(imagery["ndvi_series"])
            analysis.inferred_crops = _json_safe(crop_info["inferred_crops"])
            analysis.price_outlook = _json_safe(outlook)
            analysis.summary_text = crop_info["summary_text"]
            analysis.ai_model = crop_info["ai_model"]
            analysis.error = imagery.get("note", "")
            analysis.status = "ready"
        except Exception as exc:  # noqa: BLE001
            analysis.status = "error"
            analysis.error = f"{type(exc).__name__}: {exc}"[:500]

        analysis.updated_at = utcnow()
        session.add(analysis)
        session.commit()
