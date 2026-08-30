"""Locked-plot analysis results."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..config import get_settings
from ..deps import get_device, get_session
from ..models import Device, Plot, PlotAnalysis
from ..schemas import AnalysisOut

router = APIRouter(prefix="/api/plots", tags=["analysis"])
_settings = get_settings()
_STALE = timedelta(seconds=150)


def _needs_inline_run(analysis: PlotAnalysis | None) -> bool:
    if not _settings.inline_analysis:
        return False
    if analysis is None or analysis.status == "pending":
        return True
    if analysis.status == "running":
        updated = analysis.updated_at
        if updated and updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return not updated or datetime.now(timezone.utc) - updated > _STALE
    return False


@router.get("/{plot_id}/analysis", response_model=AnalysisOut)
async def get_analysis(
    plot_id: int,
    device: Device = Depends(get_device),
    session: Session = Depends(get_session),
):
    plot = session.get(Plot, plot_id)
    if plot is None or plot.device_id != device.id:
        raise HTTPException(404, "Plot not found")

    analysis = session.exec(
        select(PlotAnalysis).where(PlotAnalysis.plot_id == plot_id)
    ).first()

    if _needs_inline_run(analysis):
        from ..services.analysis_runner import run_analysis

        await run_analysis(plot_id)
        session.expire_all()
        analysis = session.exec(
            select(PlotAnalysis).where(PlotAnalysis.plot_id == plot_id)
        ).first()
    if analysis is None:
        return AnalysisOut(
            plot_id=plot_id,
            status="pending",
            ndvi_series=[],
            thumbnails=[],
            inferred_crops=[],
            price_outlook=[],
            summary_text="",
            ai_model="",
            error="",
        )

    return AnalysisOut(
        plot_id=plot_id,
        status=analysis.status,
        ndvi_series=analysis.ndvi_series,
        ndvi_source=analysis.ndvi_source or "",
        thumbnails=analysis.thumbnails,
        inferred_crops=analysis.inferred_crops,
        price_outlook=analysis.price_outlook,
        soil=analysis.soil or {},
        accumulated=analysis.accumulated or {},
        summary_text=analysis.summary_text,
        ai_model=analysis.ai_model,
        error=analysis.error,
        updated_at=analysis.updated_at,
    )
