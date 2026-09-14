"""Pydantic models shared by the API and the scoring engine."""
from __future__ import annotations

from datetime import date as date_type
from typing import Literal

from pydantic import BaseModel, Field

Regime = Literal["risk_on", "risk_off", "mixed", "consolidation"]


class AssetQuote(BaseModel):
    """A single normalised asset observation used by the scoring engine."""

    symbol: str
    asset_class: Literal["equity", "fx", "rates", "commodity", "crypto"]
    change_pct: float = Field(
        ...,
        description="Session change in percent, e.g. 0.85 means +0.85%.",
    )
    role: Literal["risk", "safe_haven", "usd", "yield", "commodity"] = "risk"


class MarketSnapshot(BaseModel):
    """Raw input passed from a provider into the scoring engine."""

    session: Literal["asia", "europe", "us"]
    trade_date: date_type
    quotes: list[AssetQuote]


class Driver(BaseModel):
    symbol: str
    asset_class: str
    change_pct: float
    role: str
    weight: float = Field(..., description="Contribution to the regime score.")


class Confirmation(BaseModel):
    name: str
    passed: bool
    detail: str


class Invalidation(BaseModel):
    name: str
    condition: str


class MarketPulseResponse(BaseModel):
    session: str
    trade_date: date_type
    regime: Regime
    score: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Regime score in [-1, 1]. Positive = risk on.",
    )
    headline: str
    drivers: list[Driver]
    confirmations: list[Confirmation]
    invalidations: list[Invalidation]
