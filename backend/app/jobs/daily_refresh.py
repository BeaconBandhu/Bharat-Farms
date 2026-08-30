"""Daily batch: refresh mandi prices + regional crop news.

Run directly:  python -m app.jobs.daily_refresh
On Render:     wired as a Cron Job in render.yaml
"""
from __future__ import annotations

import asyncio

import httpx
from sqlmodel import Session, select

from ..db import engine, init_db
from ..models import PlotAnalysis, Plot, WatchlistItem
from ..services import news_feed
from ..services import prices as price_svc


def _collect_targets(session: Session) -> list[tuple[str, str | None]]:
    pairs: set[tuple[str, str | None]] = set()

    for w in session.exec(select(WatchlistItem)).all():
        pairs.add((w.commodity, w.state or None))

    analyses = session.exec(select(PlotAnalysis)).all()
    plot_state = {
        p.id: p.state for p in session.exec(select(Plot)).all()
    }
    for a in analyses:
        for crop in (c.get("crop") for c in a.inferred_crops or []):
            if crop:
                pairs.add((crop, plot_state.get(a.plot_id)))

    return sorted(pairs)


async def refresh_prices(session: Session, targets: list[tuple[str, str | None]]) -> int:
    total = 0
    for commodity, state in targets:
        try:
            rows = await price_svc.fetch_agmarknet(commodity=commodity, state=state)
        except (price_svc.PricesUnavailable, httpx.HTTPError) as exc:
            print(f"  price fetch failed for {commodity}/{state}: {exc}")
            continue
        added = price_svc.upsert_snapshots(session, rows)
        total += added
        print(f"  {commodity} / {state or 'India'}: +{added} price rows")
    return total


async def refresh_news(session: Session, targets: list[tuple[str, str | None]]) -> int:
    total = 0
    for commodity, state in targets:
        try:
            items = await news_feed.fetch_feed(commodity, state)
        except Exception as exc:  # noqa: BLE001
            print(f"  news fetch failed for {commodity}/{state}: {exc}")
            continue
        added = news_feed.refresh_for_crop(session, commodity, state, items)
        total += added
        print(f"  {commodity} / {state or 'India'}: +{added} news items")
    return total


async def main() -> None:
    init_db()
    with Session(engine) as session:
        targets = _collect_targets(session)
        if not targets:
            print("No plots or watchlist entries yet - nothing to refresh.")
            return
        print(f"Refreshing {len(targets)} crop/region targets...")
        print("Prices:")
        p = await refresh_prices(session, targets)
        print("News:")
        n = await refresh_news(session, targets)
        print(f"Done. {p} new price rows, {n} new news items.")


if __name__ == "__main__":
    asyncio.run(main())
