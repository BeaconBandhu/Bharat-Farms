"""Smart crop recommendation from a short questionnaire.

Uses OpenAI when configured, otherwise returns the regional prior list so the
page still gives a useful answer.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from ..config import get_settings
from ..services import openai_client, region_priors

router = APIRouter(prefix="/api", tags=["recommend"])
_settings = get_settings()


class RecommendIn(BaseModel):
    location: str = ""
    state: str = ""
    soil_type: str = ""
    season: str = ""
    rainfall_mm: float | None = None
    land_size_ha: float | None = None
    budget_inr: float | None = None
    language: str = "en"


@router.post("/recommend")
async def recommend(payload: RecommendIn):
    priors = region_priors.likely_crops(payload.state or payload.location)

    if not _settings.openai_enabled:
        return {
            "crops": [{"crop": c, "why": "Common for this region."} for c in priors[:5]],
            "notes": "Regional prior list. Set OPENAI_API_KEY for a tailored recommendation.",
            "ai": False,
        }

    lang = openai_client.language_name(payload.language)
    system = (
        "You are an Indian agronomy advisor. Recommend crops for the coming season "
        f"given the farmer's constraints. Reply ONLY as JSON. Write the prose in {lang}."
    )
    prompt = (
        f"Location: {payload.location or payload.state or 'India'}\n"
        f"Soil: {payload.soil_type or 'unknown'}\n"
        f"Season: {payload.season or 'unknown'}\n"
        f"Rainfall: {payload.rainfall_mm or 'unknown'} mm\n"
        f"Land size: {payload.land_size_ha or 'unknown'} ha\n"
        f"Budget: Rs {payload.budget_inr or 'unknown'}\n"
        f"Regionally common crops: {', '.join(priors)}\n\n"
        'Return: {"crops":[{"crop":"...","why":"<=25 words","est_input_cost_per_acre":"Rs ...",'
        '"water_need":"low|medium|high"}],"notes":"2-3 sentences of practical advice"}\n'
        "List 3-5 crops best matched to the constraints, best first."
    )
    try:
        data = await run_in_threadpool(openai_client.chat_json, prompt, system=system)
    except openai_client.OpenAIUnavailable:
        data = {}

    crops = data.get("crops") if isinstance(data, dict) else None
    if not crops:
        return {
            "crops": [{"crop": c, "why": "Common for this region."} for c in priors[:5]],
            "notes": "Could not generate a tailored recommendation; showing regional priors.",
            "ai": False,
        }
    return {"crops": crops[:5], "notes": data.get("notes", ""), "ai": True}
