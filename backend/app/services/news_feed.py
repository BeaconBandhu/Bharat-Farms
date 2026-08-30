"""Daily regional crop news via Google News RSS + OpenAI impact labelling."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import feedparser
import httpx
from sqlmodel import Session, select

from ..config import get_settings
from ..models import NewsItem
from . import openai_client

_settings = get_settings()

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
_TAG_RE = re.compile(r"<[^>]+>")

_KEYWORDS = (
    "price OR mandi OR MSP OR procurement OR export OR import OR ban OR "
    "rain OR flood OR drought OR heatwave OR pest OR disease OR blight OR "
    "subsidy OR harvest OR sowing OR yield OR shortage OR glut"
)


def _strip_html(text: str) -> str:
    return _TAG_RE.sub("", text or "").strip()


def build_query(crop: str, state: str | None) -> str:
    region = f'("{state}" OR India)' if state else "India"
    return f'"{crop}" {region} ({_KEYWORDS})'


async def fetch_feed(crop: str, state: str | None, limit: int = 12) -> list[dict]:
    params = {
        "q": build_query(crop, state),
        "hl": "en-IN",
        "gl": "IN",
        "ceid": "IN:en",
    }
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BharatFarms/1.0)"}
    async with httpx.AsyncClient(timeout=_settings.request_timeout_seconds, headers=headers) as client:
        resp = await client.get(GOOGLE_NEWS_RSS, params=params)
        resp.raise_for_status()
        body = resp.content

    feed = feedparser.parse(body)
    items: list[dict] = []
    for entry in feed.entries[:limit]:
        published = None
        if getattr(entry, "published_parsed", None):
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        source = ""
        if getattr(entry, "source", None):
            source = getattr(entry.source, "title", "") or ""
        items.append(
            {
                "title": _strip_html(getattr(entry, "title", "")),
                "url": getattr(entry, "link", ""),
                "source": source,
                "published_at": published,
                "summary": _strip_html(getattr(entry, "summary", ""))[:500],
            }
        )
    return [i for i in items if i["title"] and i["url"]]


def classify_impact(items: list[dict], crop: str, state: str | None) -> list[dict]:
    """Label each item positive / negative / neutral for the region's growers.

    One OpenAI call for the whole batch. Falls back to neutral when the API
    is unavailable.
    """
    if not items:
        return []
    if not _settings.openai_enabled:
        return [{"impact": "neutral", "impact_reason": ""} for _ in items]

    numbered = "\n".join(
        f'{idx}. {it["title"]} — {it["summary"][:160]}' for idx, it in enumerate(items)
    )
    region = state or "India"
    system = (
        "You assess how agricultural news affects farmers growing a specific "
        "crop in a specific Indian region. Reply ONLY with JSON."
    )
    prompt = (
        f'Crop: "{crop}". Region: "{region}".\n'
        f"For each headline decide the likely effect on those farmers' income "
        f"over the next 1-3 months: \"positive\", \"negative\", or \"neutral\", "
        f"plus a <=15 word reason.\n\n"
        f"Headlines:\n{numbered}\n\n"
        'Return: {"items":[{"index":0,"impact":"positive","reason":"..."}]}'
    )
    try:
        data = openai_client.chat_json(prompt, system=system)
    except openai_client.OpenAIUnavailable:
        data = {}

    labels = {
        int(row["index"]): row
        for row in (data.get("items") or [])
        if isinstance(row, dict) and "index" in row
    }
    out: list[dict] = []
    for idx in range(len(items)):
        row = labels.get(idx, {})
        impact = str(row.get("impact", "neutral")).lower()
        if impact not in {"positive", "negative", "neutral"}:
            impact = "neutral"
        out.append({"impact": impact, "impact_reason": str(row.get("reason", ""))[:280]})
    return out


def refresh_for_crop(session: Session, crop: str, state: str | None, items: list[dict]) -> int:
    """Persist fetched+labelled items. Returns count of new rows."""
    labels = classify_impact(items, crop, state)
    inserted = 0
    for it, label in zip(items, labels):
        exists = session.exec(
            select(NewsItem.id).where(NewsItem.url == it["url"], NewsItem.crop == crop)
        ).first()
        if exists:
            continue
        session.add(
            NewsItem(
                region_state=state or "",
                crop=crop,
                title=it["title"],
                url=it["url"],
                source=it["source"],
                published_at=it["published_at"],
                summary=it["summary"],
                impact=label["impact"],
                impact_reason=label["impact_reason"],
            )
        )
        inserted += 1
    if inserted:
        session.commit()
    return inserted
