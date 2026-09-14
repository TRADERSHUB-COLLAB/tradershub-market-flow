"""Summarise a rolling window of recorded pulses.

Produces the numbers Kobus needs to decide whether Market Pulse is stable
enough to promote to the live homepage:

* regime distribution over the window
* score min / mean / max / stdev
* confirmation pass rate (any confirmation failing counts the pulse as
  unconfirmed for that check)
* day-over-day regime flip count per session
* top recurring drivers, ranked by how often they were the #1 driver
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from validation.harness import PulseRecord


@dataclass
class SessionReport:
    session: str
    n: int
    regime_counts: dict[str, int] = field(default_factory=dict)
    score_min: float = 0.0
    score_mean: float = 0.0
    score_max: float = 0.0
    score_stdev: float = 0.0
    confirmation_pass_rate: dict[str, float] = field(default_factory=dict)
    day_over_day_flips: int = 0
    top_drivers: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class WindowReport:
    trade_date_min: str | None
    trade_date_max: str | None
    total_pulses: int
    per_session: list[SessionReport]

    def to_text(self) -> str:
        lines: list[str] = []
        lines.append("Market Pulse validation report")
        lines.append("=" * 60)
        lines.append(
            f"Window: {self.trade_date_min or 'n/a'} .. "
            f"{self.trade_date_max or 'n/a'}  ({self.total_pulses} pulses)"
        )
        for s in self.per_session:
            lines.append("")
            lines.append(f"[{s.session}]  n={s.n}")
            regime_bits = ", ".join(
                f"{k}={v}" for k, v in sorted(s.regime_counts.items())
            )
            lines.append(f"  regimes: {regime_bits or 'n/a'}")
            lines.append(
                f"  score:   min={s.score_min:+.3f} mean={s.score_mean:+.3f} "
                f"max={s.score_max:+.3f} stdev={s.score_stdev:.3f}"
            )
            if s.confirmation_pass_rate:
                bits = ", ".join(
                    f"{name}={rate * 100:.0f}%"
                    for name, rate in sorted(s.confirmation_pass_rate.items())
                )
                lines.append(f"  confirmations: {bits}")
            lines.append(f"  regime flips (day-over-day): {s.day_over_day_flips}")
            if s.top_drivers:
                bits = ", ".join(f"{sym}({n})" for sym, n in s.top_drivers)
                lines.append(f"  top drivers: {bits}")
        return "\n".join(lines)


def _summarise_session(session: str, records: list[PulseRecord]) -> SessionReport:
    if not records:
        return SessionReport(session=session, n=0)

    scores = [r.score for r in records]
    regime_counts = dict(Counter(r.regime for r in records))

    confirm_totals: dict[str, int] = defaultdict(int)
    confirm_passed: dict[str, int] = defaultdict(int)
    for r in records:
        for c in r.pulse.confirmations:
            confirm_totals[c.name] += 1
            if c.passed:
                confirm_passed[c.name] += 1
    pass_rate = {
        name: confirm_passed[name] / confirm_totals[name]
        for name in confirm_totals
    }

    ordered = sorted(records, key=lambda r: r.trade_date)
    flips = sum(
        1
        for a, b in zip(ordered, ordered[1:])
        if a.regime != b.regime
    )

    top_driver_counter: Counter[str] = Counter()
    for r in records:
        if r.pulse.drivers:
            top_driver_counter[r.pulse.drivers[0].symbol] += 1
    top_drivers = top_driver_counter.most_common(5)

    stdev = statistics.pstdev(scores) if len(scores) > 1 else 0.0

    return SessionReport(
        session=session,
        n=len(records),
        regime_counts=regime_counts,
        score_min=min(scores),
        score_mean=sum(scores) / len(scores),
        score_max=max(scores),
        score_stdev=stdev,
        confirmation_pass_rate=pass_rate,
        day_over_day_flips=flips,
        top_drivers=top_drivers,
    )


def build_report(records: list[PulseRecord]) -> WindowReport:
    """Aggregate ``records`` (any order) into a :class:`WindowReport`."""
    if not records:
        return WindowReport(
            trade_date_min=None,
            trade_date_max=None,
            total_pulses=0,
            per_session=[],
        )

    by_session: dict[str, list[PulseRecord]] = defaultdict(list)
    for r in records:
        by_session[r.session].append(r)

    per_session = [
        _summarise_session(session, rows)
        for session, rows in sorted(by_session.items())
    ]

    trade_dates = sorted(r.trade_date.isoformat() for r in records)
    return WindowReport(
        trade_date_min=trade_dates[0],
        trade_date_max=trade_dates[-1],
        total_pulses=len(records),
        per_session=per_session,
    )
