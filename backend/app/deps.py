"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Depends, Header
from sqlmodel import Session

from .db import get_session
from .models import Device


def get_device_id(x_device_id: str | None = Header(default=None)) -> str:
    """Client sends a stable uuid in the `X-Device-Id` header (localStorage)."""
    return (x_device_id or "anon").strip()[:64] or "anon"


def get_device(
    device_id: str = Depends(get_device_id),
    session: Session = Depends(get_session),
) -> Device:
    device = session.get(Device, device_id)
    if device is None:
        device = Device(id=device_id)
        session.add(device)
        session.commit()
        session.refresh(device)
    return device
