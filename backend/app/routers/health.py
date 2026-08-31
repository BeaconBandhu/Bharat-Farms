"""Crop image diagnosis via OpenAI vision (replaces the old Dwani flow)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from ..services import openai_client

router = APIRouter(prefix="/api/health", tags=["crop-health"])

MAX_IMAGE_BYTES = 12 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


@router.post("/diagnose")
async def diagnose(
    file: UploadFile = File(...),
    language: str = Form("hi"),
    crop: str = Form(""),
):
    mime = file.content_type or "image/jpeg"
    if mime not in ALLOWED_MIME:
        raise HTTPException(422, "Upload a JPEG, PNG or WebP image.")
    data = await file.read()
    if not data:
        raise HTTPException(422, "Empty image upload.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image too large (max 12 MB).")

    lang = openai_client.language_name(language)
    crop_hint = f" The crop is {crop}." if crop.strip() else ""
    system = (
        "You are a plant pathologist helping Indian smallholder farmers. "
        f"Answer in {lang}, in short labelled sections."
    )
    prompt = (
        f"Examine this crop photo.{crop_hint} Identify the crop if you can, then the "
        "most likely disease, pest or deficiency, your confidence, and 2-4 concrete, "
        "low-cost management steps. If the plant looks healthy, say so. "
        "End with a one-line caution to confirm with a local extension officer."
    )
    try:
        result = await run_in_threadpool(
            openai_client.vision_analyze, data, mime, prompt, system=system
        )
    except openai_client.OpenAIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Diagnosis failed: {exc}") from exc

    return {"diagnosis": result, "language": language}
