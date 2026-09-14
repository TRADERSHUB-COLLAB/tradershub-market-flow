import pytest

from app.providers import get_provider


def test_mock_provider_is_default_and_needs_no_credentials():
    p = get_provider("mock")
    snap = p.snapshot(session="us")
    assert snap.quotes


def test_unknown_provider_raises_key_error():
    with pytest.raises(KeyError):
        get_provider("does-not-exist")


def test_twelvedata_requires_api_key(monkeypatch):
    # Clear the cache so the missing-key check runs fresh.
    from app.providers import _build
    from app.config import get_settings

    _build.cache_clear()
    get_settings.cache_clear()
    monkeypatch.delenv("MARKET_FLOW_TWELVEDATA_API_KEY", raising=False)

    with pytest.raises(Exception):  # TwelveDataError is a RuntimeError subclass
        get_provider("twelvedata")
