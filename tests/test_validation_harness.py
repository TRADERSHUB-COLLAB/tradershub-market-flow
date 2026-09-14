from datetime import date, timedelta
from pathlib import Path

from validation.harness import connect, fetch_recent, record_pulse


def _tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "pulses.sqlite"


def test_record_and_fetch(tmp_path):
    db = _tmp_db(tmp_path)
    conn = connect(db)
    rec = record_pulse(conn, session="us", on=date(2026, 9, 14))
    assert rec.session == "us"
    assert rec.trade_date == date(2026, 9, 14)
    assert rec.pulse.regime in {"risk_on", "risk_off", "mixed", "consolidation"}

    rows = fetch_recent(conn, limit=10)
    assert len(rows) == 1
    assert rows[0].session == "us"
    assert rows[0].pulse.headline == rec.pulse.headline


def test_record_is_idempotent(tmp_path):
    db = _tmp_db(tmp_path)
    conn = connect(db)
    for _ in range(3):
        record_pulse(conn, session="us", on=date(2026, 9, 14))
    rows = fetch_recent(conn, limit=10)
    assert len(rows) == 1  # unique constraint upserts, does not duplicate


def test_fetch_recent_ordering_and_session_filter(tmp_path):
    db = _tmp_db(tmp_path)
    conn = connect(db)
    start = date(2026, 9, 1)
    for i in range(3):
        d = start + timedelta(days=i)
        for s in ("asia", "europe", "us"):
            record_pulse(conn, session=s, on=d)

    us = fetch_recent(conn, limit=10, session="us")
    assert [r.trade_date for r in us] == [
        date(2026, 9, 3),
        date(2026, 9, 2),
        date(2026, 9, 1),
    ]

    all_rows = fetch_recent(conn, limit=100)
    assert len(all_rows) == 9
