import json
from datetime import date

import httpx
import pytest

from app.core.scoring import compute_pulse
from app.providers.twelvedata import (
    TwelveDataError,
    TwelveDataProvider,
    _UNIVERSE,
)


def _happy_payload() -> dict:
    """Deterministic multi-symbol response covering the full universe."""
    # Assign a stable percent_change per symbol so tests are reproducible.
    fake = {
        "SPX":     "1.20",
        "NDX":     "1.50",
        "DAX":     "0.80",
        "HSI":     "0.30",
        "DXY":     "-0.40",
        "USD/JPY": "-0.10",
        "XAU/USD": "-0.60",
        "WTI":     "0.90",
        "TNX":     "0.05",
        "BTC/USD": "2.10",
    }
    out = {}
    for sym, pct in fake.items():
        out[sym] = {
            "symbol": sym,
            "close": "100.00",
            "previous_close": "99.00",
            "percent_change": pct,
            "is_market_open": True,
        }
    return out


def _mock_client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_snapshot_maps_all_symbols_and_feeds_scoring():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/quote"
        assert request.url.params["apikey"] == "test-key"
        # All configured symbols must be batched into one call.
        requested = request.url.params["symbol"].split(",")
        assert set(requested) == {row[0] for row in _UNIVERSE}
        return httpx.Response(200, json=_happy_payload())

    client = _mock_client(handler)
    provider = TwelveDataProvider(api_key="test-key", http_client=client)

    snap = provider.snapshot(session="us", on=date(2026, 9, 14))
    assert snap.session == "us"
    assert snap.trade_date == date(2026, 9, 14)
    assert len(snap.quotes) == len(_UNIVERSE)

    # Output symbols use the TradersHub-normalised names, not TwelveData's.
    symbols = {q.symbol for q in snap.quotes}
    assert "USDJPY" in symbols and "XAUUSD" in symbols and "BTCUSD" in symbols

    # And the shape is valid for the scoring engine.
    pulse = compute_pulse(snap)
    assert pulse.regime in {"risk_on", "risk_off", "mixed", "consolidation"}
    assert -1.0 <= pulse.score <= 1.0
    assert pulse.drivers  # at least one driver


def test_snapshot_skips_symbols_with_per_symbol_errors():
    payload = _happy_payload()
    payload["WTI"] = {"status": "error", "message": "not entitled"}
    payload["TNX"] = {"symbol": "TNX", "percent_change": "not-a-number"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    provider = TwelveDataProvider(api_key="test-key", http_client=_mock_client(handler))
    snap = provider.snapshot(session="us", on=date(2026, 9, 14))
    # Both broken symbols dropped, everything else kept.
    out_symbols = {q.symbol for q in snap.quotes}
    assert "CL" not in out_symbols
    assert "US10Y" not in out_symbols
    assert len(snap.quotes) == len(_UNIVERSE) - 2


def test_top_level_error_is_surfaced():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "error", "message": "bad key"})

    provider = TwelveDataProvider(api_key="test-key", http_client=_mock_client(handler))
    with pytest.raises(TwelveDataError, match="bad key"):
        provider.snapshot(session="us", on=date(2026, 9, 14))


def test_empty_universe_response_raises():
    payload = {row[0]: {"status": "error", "message": "n/a"} for row in _UNIVERSE}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    provider = TwelveDataProvider(api_key="test-key", http_client=_mock_client(handler))
    with pytest.raises(TwelveDataError, match="no usable quotes"):
        provider.snapshot(session="us", on=date(2026, 9, 14))


def test_missing_api_key_rejected():
    with pytest.raises(TwelveDataError, match="MARKET_FLOW_TWELVEDATA_API_KEY"):
        TwelveDataProvider(api_key="")
