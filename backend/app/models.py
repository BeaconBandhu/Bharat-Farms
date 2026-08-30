"""Persistent models. SQLite-backed via SQLModel."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Device(SQLModel, table=True):
    """Anonymous browser identity (a uuid generated + stored client-side)."""

    id: str = Field(primary_key=True, max_length=64)
    created_at: datetime = Field(default_factory=utcnow)


class Plot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    device_id: str = Field(index=True, foreign_key="device.id")
    name: str
    geojson: dict = Field(default_factory=dict, sa_type=JSON)
    centroid_lat: float
    centroid_lon: float
    area_hectares: float
    state: str | None = Field(default=None, index=True)
    district: str | None = None
    locked_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


class PlotAnalysis(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    plot_id: int = Field(index=True, foreign_key="plot.id")
    status: str = Field(default="pending")  # pending | running | ready | error
    ndvi_series: list = Field(default_factory=list, sa_type=JSON)      # [{date, ndvi}]
    thumbnails: list = Field(default_factory=list, sa_type=JSON)       # [{date, url}]
    inferred_crops: list = Field(default_factory=list, sa_type=JSON)   # [{crop, confidence, seasons, reason}]
    price_outlook: list = Field(default_factory=list, sa_type=JSON)    # [{crop, direction, ...}]
    summary_text: str = Field(default="", sa_type=Text)
    ai_model: str = Field(default="")
    error: str = Field(default="", sa_type=Text)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CropPriceSnapshot(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("commodity", "market", "arrival_date", name="uq_price_snapshot"),
    )

    id: int | None = Field(default=None, primary_key=True)
    commodity: str = Field(index=True)
    variety: str = Field(default="")
    state: str = Field(default="", index=True)
    district: str = Field(default="")
    market: str = Field(default="")
    min_price: float | None = None
    max_price: float | None = None
    modal_price: float | None = None
    arrival_date: date = Field(index=True)
    fetched_at: datetime = Field(default_factory=utcnow)


class WatchlistItem(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("device_id", "commodity", "state", name="uq_watch"),
    )

    id: int | None = Field(default=None, primary_key=True)
    device_id: str = Field(index=True)
    commodity: str
    state: str = Field(default="")
    district: str = Field(default="")
    created_at: datetime = Field(default_factory=utcnow)


class NewsItem(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("url", "crop", name="uq_news"),
    )

    id: int | None = Field(default=None, primary_key=True)
    region_state: str = Field(default="", index=True)
    crop: str = Field(default="", index=True)
    title: str
    url: str
    source: str = Field(default="")
    published_at: datetime | None = Field(default=None, index=True)
    summary: str = Field(default="", sa_type=Text)
    impact: str = Field(default="neutral")  # positive | negative | neutral
    impact_reason: str = Field(default="", sa_type=Text)
    fetched_at: datetime = Field(default_factory=utcnow)
