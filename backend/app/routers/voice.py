"""Voice: OpenAI speech-to-text, text-to-speech, and a small text assistant.

Covers the major Indian languages via ISO-639-1 codes.
"""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from ..deps import get_device, get_session
from ..models import Device, NewsItem, Plot, WatchlistItem
from ..schemas import AssistantRequest, TTSRequest
from ..services import openai_client, prices as price_svc

router = APIRouter(prefix="/api/voice", tags=["voice"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024


@router.get("/languages")
def languages():
    return {"languages": openai_client.LANGUAGE_NAMES}


@router.post("/stt")
async def speech_to_text(
    file: UploadFile = File(...),
    language: str = Form("hi"),
):
    data = await file.read()
    if not data:
        raise HTTPException(422, "Empty audio upload.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio file too large (max 25 MB).")
    try:
        text = await run_in_threadpool(
            openai_client.transcribe, data, file.filename or "audio.webm", language
        )
    except openai_client.OpenAIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Transcription failed: {exc}") from exc
    return {"text": text, "language": language}


@router.post("/tts")
async def text_to_speech(payload: TTSRequest):
    lang = openai_client.language_name(payload.language)
    instructions = (
        f"Speak in {lang}. Use a clear, friendly tone suitable for a farmer. "
        "Read numbers and prices naturally."
    )
    try:
        audio = await run_in_threadpool(
            openai_client.synthesize, payload.text, payload.voice, instructions
        )
    except openai_client.OpenAIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Speech synthesis failed: {exc}") from exc
    return StreamingResponse(io.BytesIO(audio), media_type="audio/mpeg")


@router.post("/assistant")
async def assistant(
    payload: AssistantRequest,
    device: Device = Depends(get_device),
    session: Session = Depends(get_session),
):
    context = _build_context(session, device.id, payload.plot_id)
    lang = openai_client.language_name(payload.language)
    system = (
        f"You are Bharat Farms, a helpful assistant for Indian farmers. "
        f"Answer in {lang}. Be concise and practical. Use ONLY the data provided "
        f"as context; if it is missing, say so plainly."
    )
    prompt = f"Context:\n{context}\n\nFarmer's question: {payload.message}"
    try:
        reply = await run_in_threadpool(openai_client.chat, prompt, system=system)
    except openai_client.OpenAIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Assistant failed: {exc}") from exc
    return {"reply": reply, "language": payload.language}


def _build_context(session: Session, device_id: str, plot_id: int | None) -> str:
    lines: list[str] = []

    if plot_id:
        plot = session.get(Plot, plot_id)
        if plot and plot.device_id == device_id:
            lines.append(
                f"Plot '{plot.name}': {plot.area_hectares:.2f} ha in "
                f"{plot.district or '?'}, {plot.state or '?'}."
            )

    watches = session.exec(
        select(WatchlistItem).where(WatchlistItem.device_id == device_id)
    ).all()
    for w in watches[:8]:
        quote = price_svc.get_quote(session, w.commodity, w.state or None)
        if quote:
            lines.append(
                f"{w.commodity} ({w.state or 'India'}): modal Rs {quote['modal_price']}/quintal "
                f"on {quote['arrival_date']}, change {quote.get('change_pct')}%."
            )
        else:
            lines.append(f"{w.commodity} ({w.state or 'India'}): no recent price data.")

    news = session.exec(
        select(NewsItem).order_by(NewsItem.published_at.desc()).limit(6)
    ).all()
    for n in news:
        lines.append(f"News [{n.impact}] {n.crop}: {n.title}")

    return "\n".join(lines) if lines else "No saved plots, watchlist or news yet."
