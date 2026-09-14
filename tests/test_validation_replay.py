from datetime import date, timedelta

from app.core.models import MarketPulseResponse
from validation.harness import PulseRecord, connect, fetch_recent, record_pulse
from validation.replay import replay


def _seed(tmp_path, days: int = 10):
    db = tmp_path / "pulses.sqlite"
    conn = connect(db)
    start = date(2026, 9, 1)
    for i in range(days):
        record_pulse(conn, session="us", on=start + timedelta(days=i))
    return fetch_recent(conn, limit=days)


def test_replay_matches_when_engine_unchanged(tmp_path):
    records = _seed(tmp_path)
    result = replay(records)
    assert result.total == len(records)
    assert result.changed == []


def test_replay_detects_regime_change(tmp_path):
    records = _seed(tmp_path, days=3)
    # Tamper with one stored pulse to simulate a prior scoring engine that
    # disagreed with today's engine.
    original = records[0]
    mutated_pulse = original.pulse.model_copy(update={"regime": "risk_off", "score": -0.9})
    records[0] = PulseRecord(
        recorded_at_utc=original.recorded_at_utc,
        provider=original.provider,
        session=original.session,
        trade_date=original.trade_date,
        regime="risk_off",
        score=-0.9,
        headline=original.headline,
        snapshot=original.snapshot,
        pulse=mutated_pulse,
    )
    result = replay(records)
    assert len(result.changed) == 1
    diff = result.changed[0]
    assert diff.regime_changed or abs(diff.score_delta) > 1e-4
    assert isinstance(result.to_text(), str)
