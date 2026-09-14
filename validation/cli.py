"""Validation harness CLI.

Usage:

    python -m validation.cli run-day [--date YYYY-MM-DD] [--sessions asia,europe,us]
    python -m validation.cli report  [--limit 90] [--session us]
    python -m validation.cli replay  [--limit 90] [--session us]
    python -m validation.cli list    [--limit 30] [--session us]

All commands operate on ``validation/pulses.sqlite`` by default; override
with ``--db PATH``.
"""
from __future__ import annotations

import argparse
from datetime import date as date_type, datetime, timezone
from pathlib import Path

from validation.harness import (
    DEFAULT_DB_PATH,
    connect,
    fetch_recent,
    record_pulse,
)
from validation.replay import replay
from validation.report import build_report

_ALL_SESSIONS = ("asia", "europe", "us")


def _parse_date(value: str | None) -> date_type | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc).date()


def _cmd_run_day(args: argparse.Namespace) -> int:
    sessions = tuple(s.strip() for s in args.sessions.split(",") if s.strip())
    on = _parse_date(args.date)
    conn = connect(args.db)
    try:
        for session in sessions:
            rec = record_pulse(conn, session=session, on=on)
            print(
                f"[{rec.session} {rec.trade_date}] regime={rec.regime} "
                f"score={rec.score:+.3f} :: {rec.headline}"
            )
    finally:
        conn.close()
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    try:
        records = fetch_recent(conn, limit=args.limit, session=args.session)
    finally:
        conn.close()
    print(build_report(records).to_text())
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    try:
        records = fetch_recent(conn, limit=args.limit, session=args.session)
    finally:
        conn.close()
    result = replay(records)
    print(result.to_text())
    return 0 if not result.changed else 1


def _cmd_list(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    try:
        records = fetch_recent(conn, limit=args.limit, session=args.session)
    finally:
        conn.close()
    for r in records:
        print(
            f"{r.trade_date} {r.session:6s} {r.regime:14s} "
            f"score={r.score:+.3f} recorded_at={r.recorded_at_utc}"
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="validation")
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite path (default: {DEFAULT_DB_PATH})",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run-day", help="Record today's pulse(s).")
    p_run.add_argument("--date", help="Trade date (YYYY-MM-DD, UTC).")
    p_run.add_argument(
        "--sessions",
        default=",".join(_ALL_SESSIONS),
        help="Comma-separated sessions (asia,europe,us).",
    )
    p_run.set_defaults(func=_cmd_run_day)

    p_rep = sub.add_parser("report", help="Print rolling-window report.")
    p_rep.add_argument("--limit", type=int, default=90)
    p_rep.add_argument("--session", default=None)
    p_rep.set_defaults(func=_cmd_report)

    p_rep2 = sub.add_parser("replay", help="Re-score stored snapshots and diff.")
    p_rep2.add_argument("--limit", type=int, default=90)
    p_rep2.add_argument("--session", default=None)
    p_rep2.set_defaults(func=_cmd_replay)

    p_list = sub.add_parser("list", help="List recent pulses.")
    p_list.add_argument("--limit", type=int, default=30)
    p_list.add_argument("--session", default=None)
    p_list.set_defaults(func=_cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.db = Path(args.db)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
