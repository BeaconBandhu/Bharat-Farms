"""Agmarknet mandi prices via the data.gov.in OGD API.

Resource: 9ef84268-d588-465a-a308-a864a43d0070
(Current Daily Price of Various Commodities from Various Markets / Mandi)
"""
from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta, timezone

import httpx
from dateutil import parser as dateparser
from sqlalchemy import func
from sqlmodel import Session, select

from ..config import get_settings
from ..models import CropPriceSnapshot

_settings = get_settings()

RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
API_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"

# Snapshots older than this are refetched on the next request.
STALE_AFTER = timedelta(hours=6)


class PricesUnavailable(RuntimeError):
    pass


def _num(value) -> float | None:
    if value in (None, "", "NA", "-"):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _parse_date(value) -> date | None:
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    try:
        return dateparser.parse(str(value), dayfirst=True).date()
    except (ValueError, OverflowError):
        return None


def normalize_record(rec: dict) -> dict | None:
    """Map one API record to CropPriceSnapshot kwargs. Returns None if unusable."""
    def pick(*keys: str):
        for k in keys:
            if k in rec and rec[k] not in (None, ""):
                return rec[k]
        return None

    commodity = pick("commodity", "Commodity")
    arrival = _parse_date(pick("arrival_date", "Arrival_Date", "arrival_date "))
    if not commodity or not arrival:
        return None

    return {
        "commodity": str(commodity).strip().title(),
        "variety": str(pick("variety", "Variety") or "").strip(),
        "state": str(pick("state", "State") or "").strip().title(),
        "district": str(pick("district", "District") or "").strip().title(),
        "market": str(pick("market", "Market") or "").strip().title(),
        "min_price": _num(pick("min_price", "Min_Price", "min_x0020_price")),
        "max_price": _num(pick("max_price", "Max_Price", "max_x0020_price")),
        "modal_price": _num(pick("modal_price", "Modal_Price", "modal_x0020_price")),
        "arrival_date": arrival,
    }


# data.gov.in is slow and frequently 5xxs. Keep the per-request budget small and,
# after a failure, back off entirely for a while so requests stay fast.
_DATA_GOV_TIMEOUT = 12
_RETRY_STATUS = {500, 502, 503, 504}
_FAIL_COOLDOWN = timedelta(minutes=15)
_cooldown_until: datetime | None = None


def _in_cooldown() -> bool:
    return _cooldown_until is not None and datetime.now(timezone.utc) < _cooldown_until


def _note_failure() -> None:
    global _cooldown_until
    _cooldown_until = datetime.now(timezone.utc) + _FAIL_COOLDOWN


def _note_success() -> None:
    global _cooldown_until
    _cooldown_until = None


async def fetch_agmarknet(
    *,
    state: str | None = None,
    district: str | None = None,
    commodity: str | None = None,
    market: str | None = None,
    limit: int = 2000,
) -> list[dict]:
    key = _settings.data_gov_key
    if not key:
        raise PricesUnavailable("DATA_GOV_IN_API_KEY is not set")
    if _in_cooldown():
        raise PricesUnavailable("data.gov.in recently failed; backing off")

    params: dict[str, str | int] = {"api-key": key, "format": "json", "limit": limit}
    if state:
        params["filters[state]"] = state.title()
    if district:
        params["filters[district]"] = district.title()
    if commodity:
        params["filters[commodity]"] = commodity.title()
    if market:
        params["filters[market]"] = market.title()

    payload = None
    try:
        async with httpx.AsyncClient(timeout=_DATA_GOV_TIMEOUT) as client:
            for attempt in range(2):
                try:
                    resp = await client.get(API_URL, params=params)
                except httpx.HTTPError:
                    if attempt == 1:
                        raise
                    continue
                if resp.status_code in _RETRY_STATUS and attempt < 1:
                    continue
                resp.raise_for_status()
                try:
                    payload = resp.json()
                except ValueError as exc:
                    raise PricesUnavailable("data.gov.in returned non-JSON") from exc
                break
    except (httpx.HTTPError, PricesUnavailable):
        _note_failure()
        raise

    if payload is None:
        _note_failure()
        raise PricesUnavailable("data.gov.in is unavailable right now")
    _note_success()

    records = payload.get("records") or []

    # Some OGD deployments ignore server-side filters; enforce them locally too.
    def keep(r: dict) -> bool:
        if commodity and str(r.get("commodity", r.get("Commodity", ""))).strip().lower() != commodity.lower():
            return False
        if state and str(r.get("state", r.get("State", ""))).strip().lower() != state.lower():
            return False
        return True

    if commodity or state:
        records = [r for r in records if keep(r)]

    out = []
    for rec in records:
        norm = normalize_record(rec)
        if norm:
            out.append(norm)
    return out


def upsert_snapshots(session: Session, rows: list[dict]) -> int:
    inserted = 0
    for row in rows:
        exists = session.exec(
            select(CropPriceSnapshot.id).where(
                CropPriceSnapshot.commodity == row["commodity"],
                CropPriceSnapshot.market == row["market"],
                CropPriceSnapshot.arrival_date == row["arrival_date"],
            )
        ).first()
        if exists:
            continue
        session.add(CropPriceSnapshot(**row))
        inserted += 1
    if inserted:
        session.commit()
    return inserted


def _latest_fetch(session: Session, commodity: str, state: str | None) -> datetime | None:
    stmt = select(func.max(CropPriceSnapshot.fetched_at)).where(
        func.lower(CropPriceSnapshot.commodity) == commodity.lower()
    )
    if state:
        stmt = stmt.where(func.lower(CropPriceSnapshot.state) == state.lower())
    return session.exec(stmt).first()


def is_stale(session: Session, commodity: str, state: str | None) -> bool:
    last = _latest_fetch(session, commodity, state)
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last > STALE_AFTER


async def ensure_fresh(session: Session, commodity: str, state: str | None) -> None:
    """Fetch + store if we have nothing recent. Swallows upstream errors."""
    if not is_stale(session, commodity, state):
        return
    try:
        rows = await fetch_agmarknet(commodity=commodity, state=state)
        upsert_snapshots(session, rows)
    except (PricesUnavailable, httpx.HTTPError):
        pass


def _rows_for(session: Session, commodity: str, state: str | None) -> list[CropPriceSnapshot]:
    stmt = select(CropPriceSnapshot).where(
        func.lower(CropPriceSnapshot.commodity) == commodity.lower()
    )
    if state:
        stmt = stmt.where(func.lower(CropPriceSnapshot.state) == state.lower())
    stmt = stmt.order_by(CropPriceSnapshot.arrival_date.desc())
    return list(session.exec(stmt))


def get_quote(session: Session, commodity: str, state: str | None) -> dict | None:
    rows = _rows_for(session, commodity, state)
    if not rows:
        return None

    by_date: dict[date, list[float]] = {}
    for r in rows:
        if r.modal_price is not None:
            by_date.setdefault(r.arrival_date, []).append(r.modal_price)
    if not by_date:
        return None

    dates_desc = sorted(by_date, reverse=True)
    latest = dates_desc[0]
    prev = dates_desc[1] if len(dates_desc) > 1 else None

    modal = round(statistics.median(by_date[latest]), 2)
    prev_modal = round(statistics.median(by_date[prev]), 2) if prev else None
    change_abs = round(modal - prev_modal, 2) if prev_modal else None
    change_pct = (
        round((change_abs / prev_modal) * 100, 2) if prev_modal else None
    )

    latest_rows = [r for r in rows if r.arrival_date == latest]
    mins = [r.min_price for r in latest_rows if r.min_price is not None]
    maxs = [r.max_price for r in latest_rows if r.max_price is not None]
    sample = latest_rows[0]

    return {
        "commodity": sample.commodity,
        "variety": sample.variety,
        "state": sample.state or (state or ""),
        "district": sample.district,
        "market": f"{len(latest_rows)} mandi(s)",
        "modal_price": modal,
        "min_price": round(min(mins), 2) if mins else None,
        "max_price": round(max(maxs), 2) if maxs else None,
        "arrival_date": latest,
        "prev_modal_price": prev_modal,
        "change_abs": change_abs,
        "change_pct": change_pct,
    }


def get_history(
    session: Session, commodity: str, state: str | None, days: int = 45
) -> list[dict]:
    rows = _rows_for(session, commodity, state)
    cutoff = date.today() - timedelta(days=days)
    by_date: dict[date, list[float]] = {}
    for r in rows:
        if r.modal_price is not None and r.arrival_date >= cutoff:
            by_date.setdefault(r.arrival_date, []).append(r.modal_price)
    return [
        {"arrival_date": d, "modal_price": round(statistics.median(v), 2)}
        for d, v in sorted(by_date.items())
    ]
