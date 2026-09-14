/**
 * Market data providers. Same instrument universe as the Python engine so
 * switching from `mock` to `twelvedata` is a config change, not a code one.
 */
import type { AssetClass, AssetQuote, MarketSnapshot, Role, Session } from "./scoring";

// [twelvedata_symbol, output_symbol, asset_class, role]
const UNIVERSE: Array<[string, string, AssetClass, Role]> = [
  ["SPX",     "SPX",     "equity",    "risk"],
  ["NDX",     "NDX",     "equity",    "risk"],
  ["DAX",     "DAX",     "equity",    "risk"],
  ["HSI",     "HSI",     "equity",    "risk"],
  ["DXY",     "DXY",     "fx",        "usd"],
  ["USD/JPY", "USDJPY",  "fx",        "safe_haven"],
  ["XAU/USD", "XAUUSD",  "commodity", "safe_haven"],
  ["WTI",     "CL",      "commodity", "commodity"],
  ["TNX",     "US10Y",   "rates",     "yield"],
  ["BTC/USD", "BTCUSD",  "crypto",    "risk"],
];

export class ProviderError extends Error {}

export interface Provider {
  snapshot(session: Session, tradeDate: string): Promise<MarketSnapshot>;
}

// ------------------------------------------------------------------
// Mock provider — deterministic from (session, tradeDate). Used for
// vitest and local `wrangler dev` without hitting TwelveData.
// ------------------------------------------------------------------

function sha256Hex(input: string): Promise<string> {
  const enc = new TextEncoder().encode(input);
  return crypto.subtle.digest("SHA-256", enc).then((buf) =>
    Array.from(new Uint8Array(buf))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join(""),
  );
}

export class MockProvider implements Provider {
  async snapshot(session: Session, tradeDate: string): Promise<MarketSnapshot> {
    const hex = await sha256Hex(`${session}|${tradeDate}`);
    const quotes: AssetQuote[] = UNIVERSE.map(([, outSym, cls, role], i) => {
      // Two bytes per symbol into a signed percent in ~[-1.5, 1.5]
      const b = parseInt(hex.slice((2 * i * 2) % hex.length, (2 * i * 2) % hex.length + 2), 16);
      const c = parseInt(hex.slice(((2 * i + 1) * 2) % hex.length, ((2 * i + 1) * 2) % hex.length + 2), 16);
      const raw = (b - 128) + (c - 128) / 256.0;
      const change = Math.round((raw / 128) * 1.5 * 1000) / 1000;
      return { symbol: outSym, asset_class: cls, change_pct: change, role };
    });
    return { session, trade_date: tradeDate, quotes };
  }
}

// ------------------------------------------------------------------
// TwelveData provider — batches the full universe into one /quote call
// and normalises the response to AssetQuote. Per-symbol failures are
// skipped so a partial outage does not block a pulse.
// ------------------------------------------------------------------

interface TwelveDataQuote {
  symbol?: string;
  percent_change?: string;
  status?: string;
  message?: string;
}

const TD_URL = "https://api.twelvedata.com/quote";

export class TwelveDataProvider implements Provider {
  constructor(private readonly apiKey: string) {
    if (!apiKey) {
      throw new ProviderError("TWELVEDATA_API_KEY is not set");
    }
  }

  async snapshot(session: Session, tradeDate: string): Promise<MarketSnapshot> {
    const symbols = UNIVERSE.map(([tdSym]) => tdSym);
    const url = `${TD_URL}?symbol=${encodeURIComponent(symbols.join(","))}&apikey=${encodeURIComponent(this.apiKey)}`;

    const res = await fetch(url, {
      headers: { accept: "application/json" },
    });
    if (!res.ok) {
      throw new ProviderError(`TwelveData HTTP ${res.status}`);
    }
    const payload = (await res.json()) as Record<string, unknown>;

    if ((payload as TwelveDataQuote).status === "error") {
      throw new ProviderError(
        (payload as TwelveDataQuote).message ?? "TwelveData returned an error",
      );
    }

    const perSymbol: Record<string, TwelveDataQuote> = {};
    if (symbols.length === 1 && "percent_change" in payload) {
      perSymbol[symbols[0]] = payload as TwelveDataQuote;
    } else {
      for (const s of symbols) {
        perSymbol[s] = (payload[s] as TwelveDataQuote) ?? {};
      }
    }

    const quotes: AssetQuote[] = [];
    for (const [tdSym, outSym, cls, role] of UNIVERSE) {
      const q = perSymbol[tdSym];
      if (!q || q.status === "error" || q.percent_change == null) continue;
      const num = Number(q.percent_change);
      if (!Number.isFinite(num)) continue;
      quotes.push({ symbol: outSym, asset_class: cls, change_pct: num, role });
    }

    if (quotes.length === 0) {
      throw new ProviderError("TwelveData returned no usable quotes for the configured universe");
    }

    return { session, trade_date: tradeDate, quotes };
  }
}

// ------------------------------------------------------------------
// Registry
// ------------------------------------------------------------------

export function getProvider(name: string, env: Env): Provider {
  switch (name) {
    case "mock":
      return new MockProvider();
    case "twelvedata":
      return new TwelveDataProvider(env.TWELVEDATA_API_KEY ?? "");
    default:
      throw new ProviderError(`Unknown provider: ${name}`);
  }
}

// Env is declared in src/index.ts; re-declaring the shape here keeps this
// module usable in isolation for tests.
interface Env {
  TWELVEDATA_API_KEY?: string;
}
