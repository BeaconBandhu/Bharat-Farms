"""Request / response payload shapes."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# --- plots ---
class PlotCreate(BaseModel):
    name: str = Field(default="My plot", max_length=120)
    geojson: dict[str, Any]  # a GeoJSON Feature / Polygon / geometry


class PlotOut(BaseModel):
    id: int
    name: str
    geojson: dict[str, Any]
    centroid_lat: float
    centroid_lon: float
    area_hectares: float
    state: str | None
    district: str | None
    locked_at: datetime
    analysis_status: str | None = None


class AnalysisOut(BaseModel):
    plot_id: int
    status: str
    ndvi_series: list[dict[str, Any]]
    ndvi_source: str = ""
    thumbnails: list[dict[str, Any]]
    inferred_crops: list[dict[str, Any]]
    price_outlook: list[dict[str, Any]]
    soil: dict[str, Any] = {}
    accumulated: dict[str, Any] = {}
    summary_text: str
    ai_model: str
    error: str
    updated_at: datetime | None = None


# --- prices ---
class PriceQuote(BaseModel):
    commodity: str
    variety: str
    state: str
    district: str
    market: str
    modal_price: float | None
    min_price: float | None
    max_price: float | None
    arrival_date: date
    prev_modal_price: float | None = None
    change_abs: float | None = None
    change_pct: float | None = None


class PricePoint(BaseModel):
    arrival_date: date
    modal_price: float | None


class WatchCreate(BaseModel):
    commodity: str
    state: str = ""
    district: str = ""


class WatchOut(BaseModel):
    id: int
    commodity: str
    state: str
    district: str
    quote: PriceQuote | None = None


# --- news ---
class NewsOut(BaseModel):
    id: int
    region_state: str
    crop: str
    title: str
    url: str
    source: str
    published_at: datetime | None
    summary: str
    impact: str
    impact_reason: str


# --- voice ---
class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str = "hi"
    voice: str | None = None


class AssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    language: str = "hi"
    plot_id: int | None = None
