"""Plot mapping + lock."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_device, get_session
from ..models import Device, Plot, PlotAnalysis
from ..schemas import PlotCreate, PlotOut
from ..services.analysis_runner import get_or_create_analysis, run_analysis
from ..services.geocode import reverse_geocode
from ..services.geometry import polygon_stats

router = APIRouter(prefix="/api/plots", tags=["plots"])


def _to_out(plot: Plot, status: str | None) -> PlotOut:
    return PlotOut(
        id=plot.id,
        name=plot.name,
        geojson=plot.geojson,
        centroid_lat=plot.centroid_lat,
        centroid_lon=plot.centroid_lon,
        area_hectares=plot.area_hectares,
        state=plot.state,
        district=plot.district,
        locked_at=plot.locked_at,
        analysis_status=status,
    )


def _status_for(session: Session, plot_id: int) -> str | None:
    row = session.exec(
        select(PlotAnalysis.status).where(PlotAnalysis.plot_id == plot_id)
    ).first()
    return row


@router.post("", response_model=PlotOut, status_code=201)
async def create_plot(
    payload: PlotCreate,
    background: BackgroundTasks,
    device: Device = Depends(get_device),
    session: Session = Depends(get_session),
):
    try:
        stats = polygon_stats(payload.geojson)
    except ValueError as exc:
        raise HTTPException(422, f"Invalid plot geometry: {exc}") from exc

    if stats["area_hectares"] <= 0:
        raise HTTPException(422, "Plot must be a polygon with non-zero area.")
    if stats["area_hectares"] > 10_000:
        raise HTTPException(422, "Plot is unrealistically large (>10,000 ha).")

    geo = await reverse_geocode(stats["centroid_lat"], stats["centroid_lon"])

    plot = Plot(
        device_id=device.id,
        name=payload.name.strip() or "My plot",
        geojson=payload.geojson,
        centroid_lat=stats["centroid_lat"],
        centroid_lon=stats["centroid_lon"],
        area_hectares=stats["area_hectares"],
        state=geo.get("state"),
        district=geo.get("district"),
    )
    session.add(plot)
    session.commit()
    session.refresh(plot)

    get_or_create_analysis(session, plot.id)
    background.add_task(run_analysis, plot.id)

    return _to_out(plot, "pending")


@router.get("", response_model=list[PlotOut])
def list_plots(
    device: Device = Depends(get_device),
    session: Session = Depends(get_session),
):
    plots = session.exec(
        select(Plot).where(Plot.device_id == device.id).order_by(Plot.locked_at.desc())
    ).all()
    return [_to_out(p, _status_for(session, p.id)) for p in plots]


@router.get("/{plot_id}", response_model=PlotOut)
def get_plot(
    plot_id: int,
    device: Device = Depends(get_device),
    session: Session = Depends(get_session),
):
    plot = session.get(Plot, plot_id)
    if plot is None or plot.device_id != device.id:
        raise HTTPException(404, "Plot not found")
    return _to_out(plot, _status_for(session, plot_id))


@router.post("/{plot_id}/reanalyze", response_model=PlotOut)
def reanalyze_plot(
    plot_id: int,
    background: BackgroundTasks,
    device: Device = Depends(get_device),
    session: Session = Depends(get_session),
):
    plot = session.get(Plot, plot_id)
    if plot is None or plot.device_id != device.id:
        raise HTTPException(404, "Plot not found")
    analysis = get_or_create_analysis(session, plot_id)
    analysis.status = "pending"
    session.add(analysis)
    session.commit()
    background.add_task(run_analysis, plot_id)
    return _to_out(plot, "pending")


@router.delete("/{plot_id}", status_code=204)
def delete_plot(
    plot_id: int,
    device: Device = Depends(get_device),
    session: Session = Depends(get_session),
):
    plot = session.get(Plot, plot_id)
    if plot is None or plot.device_id != device.id:
        raise HTTPException(404, "Plot not found")
    if plot.agro_polygon_id:
        from ..services import agro

        agro.delete_polygon(plot.agro_polygon_id)
    for analysis in session.exec(
        select(PlotAnalysis).where(PlotAnalysis.plot_id == plot_id)
    ).all():
        session.delete(analysis)
    session.delete(plot)
    session.commit()
