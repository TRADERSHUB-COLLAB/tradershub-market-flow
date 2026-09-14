from datetime import date, timedelta

from validation.harness import connect, fetch_recent, record_pulse
from validation.report import build_report


def test_report_empty():
    r = build_report([])
    assert r.total_pulses == 0
    assert r.per_session == []
    assert "0 pulses" in r.to_text()


def test_report_over_thirty_trading_days(tmp_path):
    db = tmp_path / "pulses.sqlite"
    conn = connect(db)
    start = date(2026, 8, 1)
    for i in range(30):
        d = start + timedelta(days=i)
        for s in ("asia", "europe", "us"):
            record_pulse(conn, session=s, on=d)

    records = fetch_recent(conn, limit=200)
    assert len(records) == 90

    report = build_report(records)
    assert report.total_pulses == 90
    assert report.trade_date_min == "2026-08-01"
    assert report.trade_date_max == "2026-08-30"

    sessions = {s.session for s in report.per_session}
    assert sessions == {"asia", "europe", "us"}

    for s in report.per_session:
        assert s.n == 30
        assert -1.0 <= s.score_min <= s.score_mean <= s.score_max <= 1.0
        assert 0 <= s.day_over_day_flips <= 29
        # Every regime observed must be a legal label.
        assert set(s.regime_counts).issubset(
            {"risk_on", "risk_off", "mixed", "consolidation"}
        )

    text = report.to_text()
    assert "Market Pulse validation report" in text
    assert "[us]" in text
