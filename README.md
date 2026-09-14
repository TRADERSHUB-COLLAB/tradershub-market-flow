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
tests/
  test_health.py
  test_pulse.py
  test_scoring.py
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

## Status

This is the initial starter scaffold committed as part of the Market Flow
upgrade. The mock provider is deliberately deterministic so that the private
30-day validation harness produces reproducible pulses while real data
providers are being wired in.
