"""Regional crop news feed."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlmodel import Session, select

from ..deps import get_device, get_session
from ..models import Device, NewsItem, Plot, WatchlistItem
from ..schemas import NewsOut
from ..services import news_feed

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("", response_model=list[NewsOut])
def list_news(
    crop: str | None = None,
    state: str | None = None,
    impact: str | None = None,
    limit: int = 60,
    session: Session = Depends(get_session),
):
    stmt = select(NewsItem)
    if crop:
        stmt = stmt.where(NewsItem.crop == crop.strip().title())
    if state:
        stmt = stmt.where(NewsItem.region_state == state.strip().title())
    if impact in {"positive", "negative", "neutral"}:
        stmt = stmt.where(NewsItem.impact == impact)
    stmt = stmt.order_by(NewsItem.published_at.desc(), NewsItem.fetched_at.desc()).limit(
        min(limit, 200)
    )
    return list(session.exec(stmt))


def _targets_for_device(session: Session, device_id: str) -> list[tuple[str, str | None]]:
    """(crop, state) pairs derived from the device's plots + watchlist."""
    pairs: set[tuple[str, str | None]] = set()

    for plot in session.exec(select(Plot).where(Plot.device_id == device_id)).all():
        from ..models import PlotAnalysis

        analysis = session.exec(
            select(PlotAnalysis).where(PlotAnalysis.plot_id == plot.id)
        ).first()
        crops = [c.get("crop") for c in (analysis.inferred_crops if analysis else [])]
        for crop in crops or []:
            if crop:
                pairs.add((crop, plot.state))

    for w in session.exec(
        select(WatchlistItem).where(WatchlistItem.device_id == device_id)
    ).all():
        pairs.add((w.commodity, w.state or None))

    return sorted(pairs)[:12]


@router.post("/refresh")
async def refresh_news(
    crop: str | None = Body(default=None),
    state: str | None = Body(default=None),
    device: Device = Depends(get_device),
    session: Session = Depends(get_session),
):
    if crop:
        targets = [(crop.strip().title(), (state or "").strip().title() or None)]
    else:
        targets = _targets_for_device(session, device.id)

    if not targets:
        return {
            "new_items": 0,
            "targets": [],
            "message": "Lock a plot on the map or add a crop to your watchlist, "
            "then Fetch latest.",
        }

    total_new = 0
    refreshed: list[dict] = []
    for c, s in targets:
        try:
            items = await news_feed.fetch_feed(c, s)
        except Exception as exc:  # noqa: BLE001
            refreshed.append({"crop": c, "state": s, "error": str(exc)[:200]})
            continue
        added = news_feed.refresh_for_crop(session, c, s, items)
        total_new += added
        refreshed.append({"crop": c, "state": s, "fetched": len(items), "new": added})

    return {"new_items": total_new, "targets": refreshed}
