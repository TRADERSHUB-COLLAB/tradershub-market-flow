"""Data provider registry."""
from __future__ import annotations

from app.providers.base import MarketDataProvider
from app.providers.mock import MockProvider

_REGISTRY: dict[str, MarketDataProvider] = {
    "mock": MockProvider(),
}


def get_provider(name: str) -> MarketDataProvider:
    """Return a registered provider by name.

    Raises ``KeyError`` if the name is unknown so the caller can surface a
    clear configuration error.
    """
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(name) from exc


__all__ = ["MarketDataProvider", "MockProvider", "get_provider"]
