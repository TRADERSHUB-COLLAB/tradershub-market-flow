"""TwelveData provider.

Uses the same data source as the existing TradersHub scanner. Batches all
symbols into a single ``/quote`` call (TwelveData accepts a comma-separated
``symbol=`` list and returns a dict keyed by symbol). Maps each response to
the same normalised :class:`AssetQuote` shape the scoring engine expects.

The instrument universe intentionally mirrors the mock provider so that
switching ``MARKET_FLOW_PROVIDER=mock -> twelvedata`` does not change the
scoring engine's contract — only the source of ``change_pct``.
"""
from __future__ import annotations

from datetime import date as date_type, datetime, timezone

import httpx

from app.core.models import AssetQuote, MarketSnapshot

_BASE_URL = "https://api.twelvedata.com/quote"
_TIMEOUT_SECONDS = 10.0

# (twelvedata_symbol, output_symbol, asset_class, role)
#
# TwelveData symbol conventions used here:
#   - Cash indices via ticker: SPX, NDX, DAX, HSI
#   - FX via SLASH pairs: EUR/USD, USD/JPY, etc; DXY is an index ticker
#   - Metals via SLASH pairs: XAU/USD
#   - Energy via ticker: WTI (proxy for crude), sometimes BRENT
#   - Rates via ticker: TNX (10Y yield proxy on many feeds)
#   - Crypto via SLASH pairs: BTC/USD
_UNIVERSE: list[tuple[str, str, str, str]] = [
    ("SPX",     "SPX",     "equity",    "risk"),
    ("NDX",     "NDX",     "equity",    "risk"),
    ("DAX",     "DAX",     "equity",    "risk"),
    ("HSI",     "HSI",     "equity",    "risk"),
    ("DXY",     "DXY",     "fx",        "usd"),
    ("USD/JPY", "USDJPY",  "fx",        "safe_haven"),
    ("XAU/USD", "XAUUSD",  "commodity", "safe_haven"),
    ("WTI",     "CL",      "commodity", "commodity"),
    ("TNX",     "US10Y",   "rates",     "yield"),
    ("BTC/USD", "BTCUSD",  "crypto",    "risk"),
]


class TwelveDataError(RuntimeError):
    """Raised when the TwelveData response cannot be turned into a snapshot."""


def _parse_percent_change(payload: dict, symbol: str) -> float | None:
    """Best-effort parse of ``percent_change`` from a single-symbol payload.

    Returns ``None`` when the symbol is unavailable (missing, error status, or
    non-numeric ``percent_change``). Callers may either skip the symbol or
    surface the omission — the current provider skips, so a partial outage on
    one instrument does not prevent a pulse being computed.
    """
    if not isinstance(payload, dict):
        return None
    # TwelveData signals per-symbol errors with {"status": "error", ...}
    if payload.get("status") == "error":
        return None
    raw = payload.get("percent_change")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _extract_batch(payload: dict, symbols: list[str]) -> dict[str, dict]:
    """Normalise the /quote response to ``{symbol: payload}``.

    TwelveData returns:
      - a dict keyed by symbol when multiple symbols are requested
      - a flat single-quote dict when only one symbol is requested
      - a top-level ``{"status": "error", ...}`` on total failure
    """
    if not isinstance(payload, dict):
        raise TwelveDataError(f"Unexpected response type: {type(payload).__name__}")
    if payload.get("status") == "error":
        raise TwelveDataError(payload.get("message") or "TwelveData returned an error")

    # Single-symbol call: TD returns the quote at the top level.
    if len(symbols) == 1 and "symbol" in payload and "percent_change" in payload:
        return {symbols[0]: payload}

    # Multi-symbol call: TD keys by the requested symbol string.
    return {s: payload.get(s, {}) for s in symbols}


class TwelveDataProvider:
    """Live provider backed by the TwelveData ``/quote`` endpoint."""

    def __init__(
        self,
        api_key: str,
        universe: list[tuple[str, str, str, str]] | None = None,
        http_client: httpx.Client | None = None,
        timeout: float = _TIMEOUT_SECONDS,
    ) -> None:
        if not api_key:
            raise TwelveDataError("MARKET_FLOW_TWELVEDATA_API_KEY is not set")
        self._api_key = api_key
        self._universe = universe or _UNIVERSE
        self._client = http_client
        self._timeout = timeout
        self._owns_client = http_client is None

    def _fetch(self, symbols: list[str]) -> dict:
        params = {
            "symbol": ",".join(symbols),
            "apikey": self._api_key,
        }
        client = self._client or httpx.Client(timeout=self._timeout)
        try:
            resp = client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            return resp.json()
        finally:
            if self._owns_client and self._client is None:
                client.close()

    def snapshot(
        self,
        session: str,
        on: date_type | None = None,
    ) -> MarketSnapshot:
        trade_date = on or datetime.now(tz=timezone.utc).date()
        td_symbols = [row[0] for row in self._universe]
        payload = self._fetch(td_symbols)
        per_symbol = _extract_batch(payload, td_symbols)

        quotes: list[AssetQuote] = []
        for td_symbol, out_symbol, asset_class, role in self._universe:
            change = _parse_percent_change(per_symbol.get(td_symbol, {}), td_symbol)
            if change is None:
                continue  # skip unavailable symbol; do not fail the whole pulse
            quotes.append(
                AssetQuote(
                    symbol=out_symbol,
                    asset_class=asset_class,  # type: ignore[arg-type]
                    change_pct=change,
                    role=role,  # type: ignore[arg-type]
                )
            )

        if not quotes:
            raise TwelveDataError(
                "TwelveData returned no usable quotes for the configured universe"
            )

        return MarketSnapshot(
            session=session,  # type: ignore[arg-type]
            trade_date=trade_date,
            quotes=quotes,
        )
