"""Thin, synchronous wrappers around the OpenAI API.

Kept sync on purpose: async routes call these via
``fastapi.concurrency.run_in_threadpool`` and the analysis background job
(also sync) calls them directly. One implementation, no duplication.
"""
from __future__ import annotations

import base64
import json
from typing import Any

from openai import OpenAI

from ..config import get_settings

_settings = get_settings()
_client: OpenAI | None = None

# ISO-639-1 code -> English name, for prompts and the UI language picker.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "te": "Telugu",
    "mr": "Marathi",
    "ta": "Tamil",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "as": "Assamese",
    "ur": "Urdu",
}


class OpenAIUnavailable(RuntimeError):
    """Raised when no API key is configured."""


def language_name(code: str | None) -> str:
    return LANGUAGE_NAMES.get((code or "en").lower(), "English")


def _get_client() -> OpenAI:
    global _client
    if not _settings.openai_api_key:
        raise OpenAIUnavailable("OPENAI_API_KEY is not set")
    if _client is None:
        _client = OpenAI(
            api_key=_settings.openai_api_key,
            timeout=_settings.request_timeout_seconds,
        )
    return _client


# --------------------------------------------------------------------------- #
# Speech
# --------------------------------------------------------------------------- #
def transcribe(audio_bytes: bytes, filename: str, language: str | None = None) -> str:
    client = _get_client()
    kwargs: dict[str, Any] = {
        "model": _settings.openai_stt_model,
        "file": (filename or "audio.webm", audio_bytes),
    }
    if language:
        kwargs["language"] = language.lower()
    resp = client.audio.transcriptions.create(**kwargs)
    return (getattr(resp, "text", "") or "").strip()


def synthesize(text: str, voice: str | None = None, instructions: str | None = None) -> bytes:
    client = _get_client()
    kwargs: dict[str, Any] = {
        "model": _settings.openai_tts_model,
        "voice": voice or _settings.openai_tts_voice,
        "input": text,
        "response_format": "mp3",
    }
    if instructions:
        kwargs["instructions"] = instructions
    resp = client.audio.speech.create(**kwargs)
    # Binary response object exposes the raw bytes on `.content`.
    return resp.content


# --------------------------------------------------------------------------- #
# Vision / chat (Chat Completions - stable surface, supports image inputs)
# --------------------------------------------------------------------------- #
def _image_part(image_bytes: bytes, mime: str) -> dict:
    b64 = base64.b64encode(image_bytes).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def chat(
    prompt: str,
    *,
    system: str | None = None,
    json_mode: bool = False,
    model: str | None = None,
    images: list[tuple[bytes, str]] | None = None,
    temperature: float | None = None,
) -> str:
    client = _get_client()
    user_content: list[dict] = [{"type": "text", "text": prompt}]
    for img_bytes, mime in images or []:
        user_content.append(_image_part(img_bytes, mime))

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append(
        {"role": "user", "content": user_content if len(user_content) > 1 else prompt}
    )

    kwargs: dict[str, Any] = {
        "model": model or _settings.openai_chat_model,
        "messages": messages,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def vision_analyze(
    image_bytes: bytes,
    mime: str,
    prompt: str,
    *,
    system: str | None = None,
    json_mode: bool = False,
) -> str:
    return chat(
        prompt,
        system=system,
        json_mode=json_mode,
        model=_settings.openai_vision_model,
        images=[(image_bytes, mime)],
    )


def chat_json(prompt: str, *, system: str | None = None, model: str | None = None,
              images: list[tuple[bytes, str]] | None = None) -> Any:
    """chat() in JSON mode, parsed. Returns {} on parse failure."""
    raw = chat(prompt, system=system, json_mode=True, model=model, images=images)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
