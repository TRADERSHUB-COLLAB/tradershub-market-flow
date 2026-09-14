"""Re-score stored snapshots and diff against the recorded pulses.

Purpose: detect silent behaviour changes in the scoring engine. If the
scoring code changes between two nightly runs, running the replay against
the prior 30 trading days will surface every pulse whose regime, score,
drivers, confirmations, or invalidations no longer match.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.scoring import compute_pulse
from validation.harness import PulseRecord

SCORE_TOLERANCE = 1e-4


@dataclass
class PulseDiff:
    session: str
    trade_date: str
    regime_changed: bool
    score_delta: float
    drivers_changed: bool
    confirmations_changed: bool
    invalidations_changed: bool
    details: list[str] = field(default_factory=list)

    @property
    def any_change(self) -> bool:
        return (
            self.regime_changed
            or abs(self.score_delta) > SCORE_TOLERANCE
            or self.drivers_changed
            or self.confirmations_changed
            or self.invalidations_changed
        )


@dataclass
class ReplayReport:
    total: int
    changed: list[PulseDiff]

    def to_text(self) -> str:
        lines = [
            "Market Pulse replay diff",
            "=" * 60,
            f"Replayed {self.total} pulses; {len(self.changed)} changed.",
        ]
        for d in self.changed:
            lines.append("")
            lines.append(f"- [{d.session} {d.trade_date}]")
            for entry in d.details:
                lines.append(f"    {entry}")
        return "\n".join(lines)


def _driver_tuple(drivers) -> list[tuple]:
    return [(d.symbol, round(d.change_pct, 4), d.role, round(d.weight, 4)) for d in drivers]


def _confirmation_tuple(confs) -> list[tuple]:
    return [(c.name, c.passed) for c in confs]


def _invalidation_tuple(invs) -> list[tuple]:
    return [(i.name, i.condition) for i in invs]


def replay(records: list[PulseRecord]) -> ReplayReport:
    """Re-run scoring on each stored snapshot and diff the outputs."""
    changed: list[PulseDiff] = []
    for r in records:
        new_pulse = compute_pulse(r.snapshot)

        details: list[str] = []
        regime_changed = new_pulse.regime != r.pulse.regime
        if regime_changed:
            details.append(f"regime: {r.pulse.regime} -> {new_pulse.regime}")

        score_delta = new_pulse.score - r.pulse.score
        if abs(score_delta) > SCORE_TOLERANCE:
            details.append(
                f"score: {r.pulse.score:+.4f} -> {new_pulse.score:+.4f} "
                f"({score_delta:+.4f})"
            )

        drivers_changed = _driver_tuple(new_pulse.drivers) != _driver_tuple(r.pulse.drivers)
        if drivers_changed:
            details.append("drivers changed")

        confirmations_changed = _confirmation_tuple(new_pulse.confirmations) != _confirmation_tuple(r.pulse.confirmations)
        if confirmations_changed:
            details.append("confirmations changed")

        invalidations_changed = _invalidation_tuple(new_pulse.invalidations) != _invalidation_tuple(r.pulse.invalidations)
        if invalidations_changed:
            details.append("invalidations changed")

        diff = PulseDiff(
            session=r.session,
            trade_date=r.trade_date.isoformat(),
            regime_changed=regime_changed,
            score_delta=score_delta,
            drivers_changed=drivers_changed,
            confirmations_changed=confirmations_changed,
            invalidations_changed=invalidations_changed,
            details=details,
        )
        if diff.any_change:
            changed.append(diff)

    return ReplayReport(total=len(records), changed=changed)
