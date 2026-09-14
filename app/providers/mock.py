"""Deterministic mock provider.

The mock provider generates a reproducible snapshot from a hash of
``(session, trade_date)``. This lets the private 30-day validation harness
compare pulses over time without depending on any external data feed.
"""
from __future__ import annotations

import hashlib
from datetime import date as date_type, datetime, timezone

from app.core.models import AssetQuote, MarketSnapshot

# Symbol universe used to compute the pulse. Kept small on purpose — the
# scoring engine is happy with any subset covering the main asset classes
# and role tags.
_UNIVERSE: list[tuple[str, str, str]] = [
    # (symbol, asset_class, role)
    ("SPX", "equity", "risk"),
    ("NDX", "equity", "risk"),
    ("DAX", "equity", "risk"),
    ("HSI", "equity", "risk"),
    ("DXY", "fx", "usd"),
    ("USDJPY", "fx", "safe_haven"),
    ("XAUUSD", "commodity", "safe_haven"),
    ("CL", "commodity", "commodity"),
    ("US10Y", "rates", "yield"),
    ("BTCUSD", "crypto", "risk"),
]


def _deterministic_moves(session: str, on: date_type) -> list[float]:
    seed_src = f"{session}|{on.isoformat()}".encode()
    digest = hashlib.sha256(seed_src).digest()
    # Map two bytes per symbol into a signed percent in ~[-1.5, 1.5].
    moves: list[float] = []
    for i in range(len(_UNIVERSE)):
        b = digest[(2 * i) % len(digest)]
        c = digest[(2 * i + 1) % len(digest)]
        raw = (b - 128) + (c - 128) / 256.0
        moves.append(round(raw / 128 * 1.5, 3))
    return moves


class MockProvider:
    """Reproducible provider used by tests and the validation harness."""

    def snapshot(
        self,
        session: str,
        on: date_type | None = None,
    ) -> MarketSnapshot:
        trade_date = on or datetime.now(tz=timezone.utc).date()
        moves = _deterministic_moves(session, trade_date)
        quotes = [
            AssetQuote(
                symbol=sym,
                asset_class=cls,  # type: ignore[arg-type]
                change_pct=move,
                role=role,  # type: ignore[arg-type]
            )
            for (sym, cls, role), move in zip(_UNIVERSE, moves)
        ]
        return MarketSnapshot(
            session=session,  # type: ignore[arg-type]
            trade_date=trade_date,
            quotes=quotes,
        )
