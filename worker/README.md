# tradershub-market-flow (Cloudflare Worker)

Production runtime for TradersHub Market Flow. Serves the daily market read
at `market.tradershub.dev`.

## Endpoints

| Method | Path              | Purpose                                                          |
| ------ | ----------------- | ---------------------------------------------------------------- |
| GET    | `/v1/health`      | Liveness + config sanity check                                   |
| GET    | `/v1/pulse`       | Raw MarketPulse (regime, drivers, confirmations, invalidations)  |
| GET    | `/v1/pulse/brief` | Page-ready Brief the landing page consumes                       |

Query params on `/v1/pulse*`:
- `session` — `asia` | `europe` | `us` (defaults from UTC hour)
- `on` — `YYYY-MM-DD` (defaults to today UTC)

## Architecture

```
Landing page                Cloudflare Worker              TwelveData
                            (market.tradershub.dev)
    │                              │
    │  GET /v1/pulse/brief         │
    ├─────────────────────────────▶│
    │                              │  KV cache hit? ── yes ▶ serve
    │                              │        │
    │                              │        no
    │                              │        ▼
    │                              │  fetch /quote (batched)
    │                              │────────────────────────▶
    │                              │◀────────────────────────
    │                              │
    │                              │  compute pulse
    │                              │  store in KV (6h TTL)
    │◀─────────────────────────────│
```

A cron trigger fires at **05:00 UTC (07:00 SAST) Mon–Fri** and pre-populates
the KV cache for all three sessions, so landing-page fetches are always
warm and never wait on TwelveData.

## Local development

```bash
npm install
npm test                                # vitest — 13 unit tests
npm run typecheck                       # tsc --noEmit
PROVIDER=mock npm run dev               # wrangler dev, no external calls
```

## First deploy — one-time setup

Log in once:

```bash
npx wrangler login
```

Create the KV namespace (do it once, paste the returned id into
`wrangler.toml` under `[[kv_namespaces]]`):

```bash
npx wrangler kv:namespace create MARKET_FLOW_CACHE
```

Set the TwelveData API key as a secret (prompts for the value):

```bash
npx wrangler secret put TWELVEDATA_API_KEY
```

Deploy:

```bash
npm run deploy
```

## Custom domain

Point `market.tradershub.dev` at the Worker in the Cloudflare dashboard:

1. Workers & Pages → `tradershub-market-flow` → Settings → Triggers
2. Add Custom Domain → `market.tradershub.dev`
3. Cloudflare auto-creates the CNAME and provisions TLS

## Manual smoke test

```bash
curl https://market.tradershub.dev/v1/health
curl "https://market.tradershub.dev/v1/pulse/brief?session=us"
```

## Layout

```
src/
  index.ts        HTTP + cron entry point, KV cache
  scoring.ts      Regime scoring engine (TS port of app/core/scoring.py)
  providers.ts    MockProvider + TwelveDataProvider
  brief.ts        MarketPulse → Brief renderer (landing-page contract)
test/
  scoring.test.ts
  providers.test.ts
  brief.test.ts
```
