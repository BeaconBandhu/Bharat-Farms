"""Stock-style crop price listing + watchlist."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from ..deps import get_device, get_session
from ..models import CropPriceSnapshot, Device, WatchlistItem
from ..schemas import PricePoint, PriceQuote, WatchCreate, WatchOut
from ..services import prices as price_svc

router = APIRouter(prefix="/api", tags=["prices"])

# Common Agmarknet commodities, for the search box before the DB warms up.
COMMON_COMMODITIES = [
    "Wheat", "Rice", "Paddy", "Maize", "Bajra", "Jowar", "Barley",
    "Soybean", "Groundnut", "Mustard", "Sunflower", "Cotton",
    "Onion", "Potato", "Tomato", "Garlic", "Ginger", "Green Chilli",
    "Gram", "Tur", "Moong", "Urad", "Masur", "Bengal Gram",
    "Sugarcane", "Turmeric", "Coriander", "Cumin", "Banana", "Apple",
]


@router.get("/prices")
async def get_price(
    commodity: str = Query(..., min_length=2),
    state: str | None = None,
    session: Session = Depends(get_session),
):
    """Latest mandi quote. Always 200: `available` is false when there's no
    recent data yet (or data.gov.in is having a moment)."""
    await price_svc.ensure_fresh(session, commodity, state)
    quote = price_svc.get_quote(session, commodity, state)
    if quote is None:
        return {
            "available": False,
            "commodity": commodity,
            "reason": f"No recent mandi data for '{commodity}'"
            + (f" in {state}" if state else "")
            + " yet — data.gov.in can be slow; try again shortly.",
        }
    return {"available": True, **PriceQuote(**quote).model_dump(mode="json")}


@router.get("/prices/{commodity}/history", response_model=list[PricePoint])
async def price_history(
    commodity: str,
    state: str | None = None,
    days: int = Query(45, ge=7, le=365),
    session: Session = Depends(get_session),
):
    await price_svc.ensure_fresh(session, commodity, state)
    return [PricePoint(**p) for p in price_svc.get_history(session, commodity, state, days)]


@router.get("/commodities")
def list_commodities(
    q: str = "",
    session: Session = Depends(get_session),
):
    known = session.exec(
        select(CropPriceSnapshot.commodity).distinct()
    ).all()
    merged = sorted({*COMMON_COMMODITIES, *known})
    if q:
        ql = q.lower()
        merged = [c for c in merged if ql in c.lower()]
    return {"commodities": merged[:50]}


@router.get("/watchlist", response_model=list[WatchOut])
async def get_watchlist(
    device: Device = Depends(get_device),
    session: Session = Depends(get_session),
):
    items = session.exec(
        select(WatchlistItem)
        .where(WatchlistItem.device_id == device.id)
        .order_by(WatchlistItem.created_at.asc())
    ).all()
    out: list[WatchOut] = []
    for it in items:
        await price_svc.ensure_fresh(session, it.commodity, it.state or None)
        quote = price_svc.get_quote(session, it.commodity, it.state or None)
        out.append(
            WatchOut(
                id=it.id,
                commodity=it.commodity,
                state=it.state,
                district=it.district,
                quote=PriceQuote(**quote) if quote else None,
            )
        )
    return out


@router.post("/watchlist", response_model=WatchOut, status_code=201)
async def add_watch(
    payload: WatchCreate,
    device: Device = Depends(get_device),
    session: Session = Depends(get_session),
):
    commodity = payload.commodity.strip().title()
    state = payload.state.strip().title()
    existing = session.exec(
        select(WatchlistItem).where(
            WatchlistItem.device_id == device.id,
            func.lower(WatchlistItem.commodity) == commodity.lower(),
            func.lower(WatchlistItem.state) == state.lower(),
        )
    ).first()
    item = existing or WatchlistItem(
        device_id=device.id,
        commodity=commodity,
        state=state,
        district=payload.district.strip().title(),
    )
    if not existing:
        session.add(item)
        session.commit()
        session.refresh(item)

    await price_svc.ensure_fresh(session, item.commodity, item.state or None)
    quote = price_svc.get_quote(session, item.commodity, item.state or None)
    return WatchOut(
        id=item.id,
        commodity=item.commodity,
        state=item.state,
        district=item.district,
        quote=PriceQuote(**quote) if quote else None,
    )


@router.delete("/watchlist/{item_id}", status_code=204)
def remove_watch(
    item_id: int,
    device: Device = Depends(get_device),
    session: Session = Depends(get_session),
):
    item = session.get(WatchlistItem, item_id)
    if item is None or item.device_id != device.id:
        raise HTTPException(404, "Watchlist item not found")
    session.delete(item)
    session.commit()
