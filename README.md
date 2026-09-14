# TradersHub Market Flow

Daily market-intelligence service that describes the active market regime,
key drivers, cross-asset transmission, confirmation signals, and invalidation
levels. This repository contains the backend service that powers the Market
Pulse product line.

## What this service does

- Ingests market data from a pluggable provider interface (mock provider is
  included; production providers can be added without changing the API).
- Computes a **Market Pulse** for a session: regime label, driver ranking,
  cross-asset confirmations, and invalidation conditions.
- Exposes a small, versioned HTTP API (`/v1/...`) meant to be consumed by the
  TradersHub website, the TradingView indicator companion, and the internal
  private-validation harness during the 30-trading-day audit period.

The public TradersHub API and the TradingView indicator remain separate,
untouched products. Market Flow is built beside them, not on top of them.

## Two implementations, one contract

The repo contains two implementations of the same Market Flow engine:

- **`app/` + `validation/` (Python / FastAPI)** — the reference
  implementation and offline validation harness. Deterministic scoring,
  30-trading-day replay diff, pytest suite. Not deployed in production.
- **`worker/` (Cloudflare Worker / TypeScript)** — the production runtime
  deployed at `market.tradershub.dev`. Same scoring behaviour, ported
  line-for-line, with a KV cache and a daily cron trigger.

Behaviour changes should land in both. See `worker/README.md` for the
deploy runbook.

## Layout

```
app/
  main.py              FastAPI application factory and route registration
  config.py            Environment-driven settings
  api/
    v1/
      routes_health.py    /v1/health
      routes_pulse.py     /v1/pulse (Market Pulse endpoint)
  core/
    scoring.py          Regime scoring and driver ranking
    models.py           Pydantic request/response models
  providers/
    base.py             Provider protocol
    mock.py             Deterministic mock data provider (default)
    twelvedata.py       TwelveData /quote provider (real market data)
validation/
  harness.py          SQLite-backed recorder for daily pulses
  report.py           Rolling-window summary (regimes, scores, flips, drivers)
  replay.py           Re-score stored snapshots and diff vs recorded pulses
  cli.py              `python -m validation.cli ...` entrypoint
tests/
  test_health.py
  test_pulse.py
  test_scoring.py
  test_validation_harness.py
  test_validation_report.py
  test_validation_replay.py
  test_validation_cli.py
  test_twelvedata_provider.py
  test_provider_registry.py
requirements.txt
pyproject.toml
.env.example
```

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Then open `http://localhost:8000/docs` for the interactive schema.

## Running tests

```bash
pip install -r requirements.txt
pytest -q
```

## Providers

Two providers ship with the service:

- **`mock`** (default) — deterministic, seeded from `(session, trade_date)`.
  Used by tests, CI, and any local run without credentials.
- **`twelvedata`** — real market data via TwelveData's `/quote` endpoint,
  the same source the existing TradersHub scanner already trusts.

Switch by setting environment variables:

```bash
export MARKET_FLOW_PROVIDER=twelvedata
export MARKET_FLOW_TWELVEDATA_API_KEY=your_key_here
```

The TwelveData provider batches the full instrument universe into a single
`/quote` call and normalises each response to the same `AssetQuote` shape
the scoring engine expects, so switching providers is a config change, not
a code change. Per-symbol failures (e.g. one instrument temporarily
unavailable on your plan) are skipped so a partial outage does not block a
pulse; a total-response error is surfaced.

## Private 30-trading-day validation harness

Before Market Pulse touches the live homepage it runs privately for 30
trading days. The harness lives under `validation/` and is driven by a
single CLI:

```bash
# Nightly (cron or manual): record today's pulses for all three sessions.
python -m validation.cli run-day

# Same, but for a specific historic date and only the US session.
python -m validation.cli run-day --date 2026-09-14 --sessions us

# Rolling summary over the last N pulses (default 90 = 30 trading days x 3 sessions).
python -m validation.cli report --limit 90

# Re-score every stored snapshot with the current engine and print any diffs.
# Exits non-zero if any pulse changed, so it plugs straight into CI.
python -m validation.cli replay --limit 90

# Peek at recent rows.
python -m validation.cli list --limit 30
```

Data is stored in `validation/pulses.sqlite` by default (override with
`--db`). The `(provider, session, trade_date)` triple is unique, so
nightly re-runs are idempotent. The report covers regime distribution,
score min/mean/max/stdev, confirmation pass rate, day-over-day regime
flips per session, and the top recurring drivers. The replay is what
catches silent scoring changes between engine revisions.

## Status

This is the initial starter scaffold plus the private validation harness.
The mock provider is deliberately deterministic so that the 30-day
validation window produces reproducible pulses while real data providers
are being wired in.
