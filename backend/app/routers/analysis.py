"""Locked-plot analysis results."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_device, get_session
from ..models import Device, Plot, PlotAnalysis
from ..schemas import AnalysisOut

router = APIRouter(prefix="/api/plots", tags=["analysis"])


@router.get("/{plot_id}/analysis", response_model=AnalysisOut)
def get_analysis(
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
