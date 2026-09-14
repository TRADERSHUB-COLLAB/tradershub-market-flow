import { afterEach, describe, expect, it, vi } from "vitest";
import { MockProvider, ProviderError, TwelveDataProvider } from "../src/providers";

describe("MockProvider", () => {
  it("returns a deterministic snapshot", async () => {
    const p = new MockProvider();
    const a = await p.snapshot("us", "2026-09-14");
    const b = await p.snapshot("us", "2026-09-14");
    expect(a).toEqual(b);
    expect(a.quotes.length).toBeGreaterThan(0);
    for (const q of a.quotes) {
      expect(Math.abs(q.change_pct)).toBeLessThan(2);
    }
  });
});

describe("TwelveDataProvider", () => {
  const realFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = realFetch;
    vi.restoreAllMocks();
  });

  it("throws when api key missing", () => {
    expect(() => new TwelveDataProvider("")).toThrow(ProviderError);
  });

  it("parses a multi-symbol response and skips per-symbol errors", async () => {
    const payload: Record<string, unknown> = {
      SPX:   { symbol: "SPX", percent_change: "1.20" },
      NDX:   { symbol: "NDX", percent_change: "1.50" },
      DAX:   { symbol: "DAX", percent_change: "0.80" },
      HSI:   { symbol: "HSI", percent_change: "0.30" },
      DXY:   { symbol: "DXY", percent_change: "-0.40" },
      "USD/JPY": { symbol: "USDJPY", percent_change: "-0.10" },
      "XAU/USD": { symbol: "XAUUSD", percent_change: "-0.60" },
      WTI:   { status: "error", message: "not entitled" },        // dropped
      TNX:   { symbol: "TNX", percent_change: "not-a-number" },   // dropped
      "BTC/USD": { symbol: "BTC/USD", percent_change: "2.10" },
    };
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const p = new TwelveDataProvider("test-key");
    const snap = await p.snapshot("us", "2026-09-14");
    const symbols = snap.quotes.map((q) => q.symbol);
    expect(symbols).toContain("USDJPY");
    expect(symbols).toContain("XAUUSD");
    expect(symbols).toContain("BTCUSD");
    expect(symbols).not.toContain("CL");      // WTI dropped
    expect(symbols).not.toContain("US10Y");   // TNX dropped
  });

  it("surfaces a top-level error", async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ status: "error", message: "bad key" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const p = new TwelveDataProvider("test-key");
    await expect(p.snapshot("us", "2026-09-14")).rejects.toThrow(/bad key/);
  });

  it("rejects a fully unusable response", async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({
        SPX: { status: "error" }, NDX: { status: "error" }, DAX: { status: "error" },
        HSI: { status: "error" }, DXY: { status: "error" },
        "USD/JPY": { status: "error" }, "XAU/USD": { status: "error" },
        WTI: { status: "error" }, TNX: { status: "error" }, "BTC/USD": { status: "error" },
      }), { status: 200, headers: { "content-type": "application/json" } }),
    );
    const p = new TwelveDataProvider("test-key");
    await expect(p.snapshot("us", "2026-09-14")).rejects.toThrow(/no usable quotes/);
  });
});
