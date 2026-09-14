"""Regime scoring and driver ranking for the Market Pulse.

The scoring engine is intentionally simple and deterministic. It maps a
:class:`MarketSnapshot` into a :class:`MarketPulseResponse` by:

1. Assigning each quote a *risk polarity* based on its role
   (risk-on assets score positively when up, safe havens score positively
   when down, USD scores negatively when up, etc.).
2. Weighting each contribution by the absolute size of the session move,
   normalising by the total moved so the aggregate lives in ``[-1, 1]``.
3. Mapping the aggregate score to a regime label with hysteresis bands.
4. Ranking the top contributing quotes as drivers, then attaching two
   confirmation checks and two invalidation conditions that the trader can
   monitor intraday.
"""
from __future__ import annotations

from app.core.models import (
    AssetQuote,
    Confirmation,
    Driver,
    Invalidation,
    MarketPulseResponse,
    MarketSnapshot,
    Regime,
)

# Role -> sign applied to change_pct when contributing to the risk score.
_ROLE_POLARITY: dict[str, float] = {
    "risk": 1.0,
    "safe_haven": -1.0,
    "usd": -1.0,
    "yield": -0.5,
    "commodity": 0.5,
}


def _polarity(role: str) -> float:
    return _ROLE_POLARITY.get(role, 0.0)


def _regime_from_score(score: float) -> Regime:
    if score >= 0.35:
        return "risk_on"
    if score <= -0.35:
        return "risk_off"
    if abs(score) < 0.10:
        return "consolidation"
    return "mixed"


def _headline(regime: Regime, score: float, top: AssetQuote | None) -> str:
    pct = f"{score * 100:+.0f}"
    if top is None:
        return f"{regime.replace('_', ' ').title()} regime (score {pct})."
    lead = f"{top.symbol} {top.change_pct:+.2f}%"
    if regime == "risk_on":
        return f"Risk-on tone with {lead} leading (score {pct})."
    if regime == "risk_off":
        return f"Defensive tone with {lead} leading (score {pct})."
    if regime == "consolidation":
        return f"Range / consolidation, {lead} in focus (score {pct})."
    return f"Mixed cross-asset picture, {lead} in focus (score {pct})."


def compute_pulse(snapshot: MarketSnapshot) -> MarketPulseResponse:
    """Turn a raw snapshot into a Market Pulse response."""
    quotes = snapshot.quotes

    weighted_contribs: list[tuple[AssetQuote, float]] = []
    total_abs_move = 0.0
    for q in quotes:
        move = abs(q.change_pct)
        total_abs_move += move
        weighted_contribs.append((q, _polarity(q.role) * q.change_pct))

    raw_score = sum(c for _, c in weighted_contribs)
    denom = total_abs_move if total_abs_move > 0 else 1.0
    score = max(-1.0, min(1.0, raw_score / denom))

    # Minimum-activity floor: if the whole tape barely moved, damp the score
    # so noise resolves to consolidation instead of registering a false regime.
    _MIN_ACTIVITY = 0.25  # aggregate abs %-move across all quotes
    if total_abs_move < _MIN_ACTIVITY:
        score *= total_abs_move / _MIN_ACTIVITY

    ranked = sorted(
        weighted_contribs,
        key=lambda item: abs(item[1]),
        reverse=True,
    )
    top_quote = ranked[0][0] if ranked else None

    drivers = [
        Driver(
            symbol=q.symbol,
            asset_class=q.asset_class,
            change_pct=q.change_pct,
            role=q.role,
            weight=round(abs(contrib) / denom, 4),
        )
        for q, contrib in ranked[:5]
    ]

    regime = _regime_from_score(score)

    equities = [q for q in quotes if q.asset_class == "equity"]
    usd = next(
        (q for q in quotes if q.asset_class == "fx" and q.role == "usd"),
        None,
    )
    yields = [q for q in quotes if q.asset_class == "rates"]

    confirmations: list[Confirmation] = []
    if equities:
        equity_up = sum(1 for q in equities if q.change_pct > 0)
        confirmations.append(
            Confirmation(
                name="equity_breadth",
                passed=(
                    (regime == "risk_on" and equity_up >= len(equities) / 2)
                    or (regime == "risk_off" and equity_up <= len(equities) / 2)
                    or regime in {"mixed", "consolidation"}
                ),
                detail=(
                    f"{equity_up}/{len(equities)} tracked equity indices "
                    "moved in the direction of the regime."
                ),
            )
        )
    if usd is not None:
        confirmations.append(
            Confirmation(
                name="usd_alignment",
                passed=(
                    (regime == "risk_on" and usd.change_pct <= 0)
                    or (regime == "risk_off" and usd.change_pct >= 0)
                    or regime in {"mixed", "consolidation"}
                ),
                detail=f"USD proxy {usd.symbol} at {usd.change_pct:+.2f}%.",
            )
        )

    invalidations: list[Invalidation] = [
        Invalidation(
            name="regime_flip",
            condition=(
                "Score crosses zero and holds for more than 30 minutes "
                "with equity breadth reversing."
            ),
        ),
        Invalidation(
            name="driver_fade",
            condition=(
                f"Top driver {top_quote.symbol if top_quote else 'n/a'} "
                "gives back more than 50% of its session move."
            ),
        ),
    ]

    return MarketPulseResponse(
        session=snapshot.session,
        trade_date=snapshot.trade_date,
        regime=regime,
        score=round(score, 4),
        headline=_headline(regime, score, top_quote),
        drivers=drivers,
        confirmations=confirmations,
        invalidations=invalidations,
    )
