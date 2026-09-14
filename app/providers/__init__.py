"""Data provider registry.

Providers are built lazily so that the mock path never needs credentials and
so that switching ``MARKET_FLOW_PROVIDER`` is a config change, not a code one.
"""
from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.providers.base import MarketDataProvider
from app.providers.mock import MockProvider

__all__ = ["MarketDataProvider", "MockProvider", "get_provider"]


@lru_cache
def _build(name: str) -> MarketDataProvider:
    if name == "mock":
        return MockProvider()
    if name == "twelvedata":
        # Imported lazily to avoid pulling httpx at import time for mock users.
        from app.providers.twelvedata import TwelveDataProvider

        settings = get_settings()
        return TwelveDataProvider(api_key=settings.twelvedata_api_key or "")
    raise KeyError(name)


def get_provider(name: str) -> MarketDataProvider:
    """Return a provider by name; raises ``KeyError`` for unknown names."""
    return _build(name)
