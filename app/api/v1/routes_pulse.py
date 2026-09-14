"""Market Pulse endpoint."""
from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.core.models import MarketPulseResponse
from app.core.scoring import compute_pulse
from app.providers import get_provider

router = APIRouter(tags=["pulse"])


@router.get("/pulse", response_model=MarketPulseResponse)
def pulse(
    session: str = Query(
        "us",
        pattern="^(asia|europe|us)$",
        description="Trading session the pulse should describe.",
    ),
    on: date_type | None = Query(
        None,
        description="Trading date (YYYY-MM-DD). Defaults to today (UTC).",
    ),
) -> MarketPulseResponse:
    settings = get_settings()
    try:
        provider = get_provider(settings.provider)
    except KeyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unknown provider configured: {settings.provider!r}",
        ) from exc

    snapshot = provider.snapshot(session=session, on=on)
    return compute_pulse(snapshot)
