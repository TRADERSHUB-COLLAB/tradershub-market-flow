"""Provider protocol."""
from __future__ import annotations

from datetime import date as date_type
from typing import Protocol

from app.core.models import MarketSnapshot


class MarketDataProvider(Protocol):
    """Anything that can supply a normalised :class:`MarketSnapshot`."""

    def snapshot(
        self,
        session: str,
        on: date_type | None = None,
    ) -> MarketSnapshot:
        """Return the market snapshot for ``session`` on ``on`` (UTC)."""
        ...
