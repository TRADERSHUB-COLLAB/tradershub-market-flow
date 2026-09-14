/**
 * TradersHub Market Flow — Cloudflare Worker entry point.
 *
 * Routes:
 *   GET /v1/health         → { ok: true, ... }
 *   GET /v1/pulse          → raw MarketPulse (JSON)
 *   GET /v1/pulse/brief    → page-ready Brief (JSON) — what the landing page fetches
 *
 * Cron (see wrangler.toml):
 *   0 5 * * 1-5 UTC  → records the day's pulse into KV so the endpoints
 *                      serve cached results instead of hitting TwelveData
 *                      on every landing-page load.
 */
import { toBrief, type Brief } from "./brief";
import { getProvider, ProviderError } from "./providers";
import { computePulse, type MarketPulse, type Session } from "./scoring";

export interface Env {
  PROVIDER: string;
  CORS_ORIGIN: string;
  TWELVEDATA_API_KEY?: string;
  CACHE: KVNamespace;
}

const CACHE_TTL_SECONDS = 6 * 60 * 60; // 6h — cron refreshes long before this.

// ---- helpers -----------------------------------------------------

function todayUtcISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function sessionFromUtcHour(hour: number): Session {
  // Rough session mapping so a request outside cron gets a sensible default.
  if (hour < 7) return "asia";
  if (hour < 14) return "europe";
  return "us";
}

function corsHeaders(env: Env, extra: Record<string, string> = {}): Headers {
  const h = new Headers({
    "access-control-allow-origin": env.CORS_ORIGIN,
    "access-control-allow-methods": "GET, OPTIONS",
    "access-control-allow-headers": "content-type",
    "access-control-max-age": "86400",
    "vary": "origin",
    ...extra,
  });
  return h;
}

function jsonResponse(body: unknown, env: Env, status = 200): Response {
  const h = corsHeaders(env, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "public, max-age=300, s-maxage=300",
  });
  return new Response(JSON.stringify(body), { status, headers: h });
}

function errorResponse(message: string, env: Env, status = 500): Response {
  return jsonResponse({ error: message }, env, status);
}

// ---- core pulse fetch, with KV cache ----------------------------

interface CachedEntry {
  pulse: MarketPulse;
  recorded_at: string;
}

async function getOrComputePulse(
  env: Env,
  session: Session,
  tradeDate: string,
): Promise<CachedEntry> {
  const key = `pulse:${env.PROVIDER}:${session}:${tradeDate}`;

  const cached = await env.CACHE.get<CachedEntry>(key, "json");
  if (cached) return cached;

  const provider = getProvider(env.PROVIDER, env);
  const snapshot = await provider.snapshot(session, tradeDate);
  const pulse = computePulse(snapshot);
  const entry: CachedEntry = {
    pulse,
    recorded_at: new Date().toISOString(),
  };
  await env.CACHE.put(key, JSON.stringify(entry), {
    expirationTtl: CACHE_TTL_SECONDS,
  });
  return entry;
}

// ---- HTTP handler -----------------------------------------------

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(env) });
    }
    if (request.method !== "GET") {
      return errorResponse("Method not allowed", env, 405);
    }

    // /v1/health
    if (url.pathname === "/v1/health") {
      return jsonResponse(
        {
          ok: true,
          service: "tradershub-market-flow",
          provider: env.PROVIDER,
          time: new Date().toISOString(),
        },
        env,
      );
    }

    // /v1/pulse and /v1/pulse/brief
    if (url.pathname === "/v1/pulse" || url.pathname === "/v1/pulse/brief") {
      const session = (url.searchParams.get("session") as Session) ??
        sessionFromUtcHour(new Date().getUTCHours());
      const tradeDate = url.searchParams.get("on") ?? todayUtcISO();

      if (!["asia", "europe", "us"].includes(session)) {
        return errorResponse(`Invalid session: ${session}`, env, 400);
      }

      try {
        const { pulse, recorded_at } = await getOrComputePulse(env, session, tradeDate);
        if (url.pathname === "/v1/pulse") {
          return jsonResponse({ ...pulse, recorded_at }, env);
        }
        const brief: Brief = toBrief(pulse, new Date(recorded_at));
        return jsonResponse(brief, env);
      } catch (err) {
        if (err instanceof ProviderError) {
          return errorResponse(err.message, env, 502);
        }
        console.error(err);
        return errorResponse("Failed to compute pulse", env, 500);
      }
    }

    if (url.pathname === "/" || url.pathname === "") {
      return jsonResponse(
        {
          service: "tradershub-market-flow",
          endpoints: ["/v1/health", "/v1/pulse", "/v1/pulse/brief"],
        },
        env,
      );
    }

    return errorResponse("Not found", env, 404);
  },

  // ---- Cron: record the day's pulse across sessions -----------
  async scheduled(_controller: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    const tradeDate = todayUtcISO();
    const sessions: Session[] = ["asia", "europe", "us"];
    ctx.waitUntil(
      (async () => {
        for (const session of sessions) {
          try {
            const key = `pulse:${env.PROVIDER}:${session}:${tradeDate}`;
            const provider = getProvider(env.PROVIDER, env);
            const snapshot = await provider.snapshot(session, tradeDate);
            const pulse = computePulse(snapshot);
            const entry: CachedEntry = {
              pulse,
              recorded_at: new Date().toISOString(),
            };
            await env.CACHE.put(key, JSON.stringify(entry), {
              expirationTtl: CACHE_TTL_SECONDS,
            });
            console.log(
              `[cron] recorded pulse ${session} ${tradeDate} regime=${pulse.regime} score=${pulse.score}`,
            );
          } catch (err) {
            console.error(`[cron] failed for ${session}:`, err);
          }
        }
      })(),
    );
  },
};
