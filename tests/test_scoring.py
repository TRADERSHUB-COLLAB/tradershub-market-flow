from datetime import date

from app.core.models import AssetQuote, MarketSnapshot
from app.core.scoring import compute_pulse


def _snap(quotes):
    return MarketSnapshot(session="us", trade_date=date(2026, 9, 14), quotes=quotes)


def test_risk_on_regime():
    snap = _snap([
        AssetQuote(symbol="SPX", asset_class="equity", change_pct=1.2, role="risk"),
        AssetQuote(symbol="NDX", asset_class="equity", change_pct=1.5, role="risk"),
        AssetQuote(symbol="DXY", asset_class="fx", change_pct=-0.4, role="usd"),
        AssetQuote(symbol="XAUUSD", asset_class="commodity", change_pct=-0.6, role="safe_haven"),
    ])
    pulse = compute_pulse(snap)
    assert pulse.regime == "risk_on"
    assert pulse.score > 0
    assert pulse.drivers[0].symbol in {"NDX", "SPX", "XAUUSD"}


def test_risk_off_regime():
    snap = _snap([
        AssetQuote(symbol="SPX", asset_class="equity", change_pct=-1.4, role="risk"),
        AssetQuote(symbol="NDX", asset_class="equity", change_pct=-1.6, role="risk"),
        AssetQuote(symbol="DXY", asset_class="fx", change_pct=0.5, role="usd"),
        AssetQuote(symbol="XAUUSD", asset_class="commodity", change_pct=0.9, role="safe_haven"),
    ])
    pulse = compute_pulse(snap)
    assert pulse.regime == "risk_off"
    assert pulse.score < 0


def test_consolidation_regime_when_flat():
    snap = _snap([
        AssetQuote(symbol="SPX", asset_class="equity", change_pct=0.02, role="risk"),
        AssetQuote(symbol="DXY", asset_class="fx", change_pct=-0.01, role="usd"),
    ])
    pulse = compute_pulse(snap)
    assert pulse.regime in {"consolidation", "mixed"}
    assert -1.0 <= pulse.score <= 1.0


def test_score_bounded():
    snap = _snap([
        AssetQuote(symbol="X", asset_class="equity", change_pct=999.0, role="risk"),
    ])
    pulse = compute_pulse(snap)
    assert -1.0 <= pulse.score <= 1.0
