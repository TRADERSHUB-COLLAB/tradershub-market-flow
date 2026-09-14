"""SQLite-backed store for Market Pulse validation runs.

Schema (single table, on purpose — this is a private, throwaway harness):

    pulses(
        id                INTEGER PRIMARY KEY,
        recorded_at_utc   TEXT    NOT NULL,   -- ISO-8601 timestamp
        provider          TEXT    NOT NULL,
        session           TEXT    NOT NULL,   -- asia | europe | us
        trade_date        TEXT    NOT NULL,   -- YYYY-MM-DD
        regime            TEXT    NOT NULL,
        score             REAL    NOT NULL,
        headline          TEXT    NOT NULL,
        snapshot_json     TEXT    NOT NULL,   -- raw MarketSnapshot
        pulse_json        TEXT    NOT NULL,   -- full MarketPulseResponse
        UNIQUE(provider, session, trade_date)
    )

The ``UNIQUE`` constraint lets a nightly re-run be idempotent: the same
(provider, session, trade_date) triplet is upserted rather than duplicated.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date as date_type, datetime, timezone
from pathlib import Path
from typing import Iterable

from app.config import get_settings
from app.core.models import MarketPulseResponse, MarketSnapshot
from app.core.scoring import compute_pulse
from app.providers import get_provider

DEFAULT_DB_PATH = Path("validation/pulses.sqlite")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pulses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at_utc TEXT NOT NULL,
    provider        TEXT NOT NULL,
    session         TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    regime          TEXT NOT NULL,
    score           REAL NOT NULL,
    headline        TEXT NOT NULL,
    snapshot_json   TEXT NOT NULL,
    pulse_json      TEXT NOT NULL,
    UNIQUE(provider, session, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_pulses_trade_date ON pulses(trade_date);
CREATE INDEX IF NOT EXISTS idx_pulses_session    ON pulses(session);
"""


@dataclass(frozen=True)
class PulseRecord:
    """A row read back from the harness store."""

    recorded_at_utc: str
    provider: str
    session: str
    trade_date: date_type
    regime: str
    score: float
    headline: str
    snapshot: MarketSnapshot
    pulse: MarketPulseResponse


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open (and initialise) the harness database."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def record_pulse(
    conn: sqlite3.Connection,
    session: str,
    on: date_type | None = None,
    provider_name: str | None = None,
) -> PulseRecord:
    """Compute and persist the pulse for ``session`` on ``on``.

    Existing rows for the same (provider, session, trade_date) are replaced
    so nightly cron re-runs stay idempotent.
    """
    settings = get_settings()
    provider = get_provider(provider_name or settings.provider)
    snapshot = provider.snapshot(session=session, on=on)
    pulse = compute_pulse(snapshot)

    recorded_at = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    row = (
        recorded_at,
        provider_name or settings.provider,
        snapshot.session,
        snapshot.trade_date.isoformat(),
        pulse.regime,
        pulse.score,
        pulse.headline,
        snapshot.model_dump_json(),
        pulse.model_dump_json(),
    )

    conn.execute(
        """
        INSERT INTO pulses
            (recorded_at_utc, provider, session, trade_date,
             regime, score, headline, snapshot_json, pulse_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider, session, trade_date) DO UPDATE SET
            recorded_at_utc = excluded.recorded_at_utc,
            regime          = excluded.regime,
            score           = excluded.score,
            headline        = excluded.headline,
            snapshot_json   = excluded.snapshot_json,
            pulse_json      = excluded.pulse_json
        """,
        row,
    )
    conn.commit()

    return PulseRecord(
        recorded_at_utc=recorded_at,
        provider=row[1],
        session=snapshot.session,
        trade_date=snapshot.trade_date,
        regime=pulse.regime,
        score=pulse.score,
        headline=pulse.headline,
        snapshot=snapshot,
        pulse=pulse,
    )


def _row_to_record(row: sqlite3.Row) -> PulseRecord:
    snap = MarketSnapshot.model_validate_json(row["snapshot_json"])
    pulse = MarketPulseResponse.model_validate_json(row["pulse_json"])
    return PulseRecord(
        recorded_at_utc=row["recorded_at_utc"],
        provider=row["provider"],
        session=row["session"],
        trade_date=date_type.fromisoformat(row["trade_date"]),
        regime=row["regime"],
        score=row["score"],
        headline=row["headline"],
        snapshot=snap,
        pulse=pulse,
    )


def fetch_recent(
    conn: sqlite3.Connection,
    limit: int = 30,
    session: str | None = None,
    provider: str | None = None,
) -> list[PulseRecord]:
    """Return the most recent pulses, newest trade_date first."""
    sql = "SELECT * FROM pulses"
    clauses: list[str] = []
    params: list[object] = []
    if session:
        clauses.append("session = ?")
        params.append(session)
    if provider:
        clauses.append("provider = ?")
        params.append(provider)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY trade_date DESC, session ASC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_record(r) for r in rows]


def fetch_all(conn: sqlite3.Connection) -> Iterable[PulseRecord]:
    for row in conn.execute("SELECT * FROM pulses ORDER BY trade_date, session"):
        yield _row_to_record(row)
