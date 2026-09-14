import { describe, expect, it } from "vitest";
import { computePulse, type AssetQuote, type MarketSnapshot } from "../src/scoring";

function snap(quotes: AssetQuote[]): MarketSnapshot {
  return { session: "us", trade_date: "2026-09-14", quotes };
}

describe("computePulse", () => {
  it("returns risk_on when equities up and havens down", () => {
    const s = snap([
      { symbol: "SPX", asset_class: "equity", change_pct: 1.2, role: "risk" },
      { symbol: "NDX", asset_class: "equity", change_pct: 1.5, role: "risk" },
      { symbol: "DXY", asset_class: "fx",     change_pct: -0.4, role: "usd" },
      { symbol: "XAU", asset_class: "commodity", change_pct: -0.6, role: "safe_haven" },
    ]);
    const p = computePulse(s);
    expect(p.regime).toBe("risk_on");
    expect(p.score).toBeGreaterThan(0);
    expect(p.drivers.length).toBeGreaterThan(0);
    expect(p.confirmations.length).toBeGreaterThan(0);
  });

  it("returns risk_off when equities down and havens up", () => {
    const s = snap([
      { symbol: "SPX", asset_class: "equity", change_pct: -1.4, role: "risk" },
      { symbol: "NDX", asset_class: "equity", change_pct: -1.6, role: "risk" },
      { symbol: "DXY", asset_class: "fx",     change_pct: 0.5,  role: "usd" },
      { symbol: "XAU", asset_class: "commodity", change_pct: 0.9, role: "safe_haven" },
    ]);
    const p = computePulse(s);
    expect(p.regime).toBe("risk_off");
    expect(p.score).toBeLessThan(0);
  });

  it("consolidates on quiet tape", () => {
    const p = computePulse(
      snap([
        { symbol: "SPX", asset_class: "equity", change_pct: 0.02, role: "risk" },
        { symbol: "DXY", asset_class: "fx",     change_pct: -0.01, role: "usd" },
      ]),
    );
    expect(["consolidation", "mixed"]).toContain(p.regime);
    expect(p.score).toBeGreaterThanOrEqual(-1);
    expect(p.score).toBeLessThanOrEqual(1);
  });

  it("bounds score to [-1, 1] even with absurd inputs", () => {
    const p = computePulse(
      snap([{ symbol: "X", asset_class: "equity", change_pct: 999, role: "risk" }]),
    );
    expect(p.score).toBeGreaterThanOrEqual(-1);
    expect(p.score).toBeLessThanOrEqual(1);
  });

  it("headline mentions the top driver", () => {
    const p = computePulse(
      snap([
        { symbol: "NDX", asset_class: "equity", change_pct: 2.1, role: "risk" },
        { symbol: "SPX", asset_class: "equity", change_pct: 1.2, role: "risk" },
      ]),
    );
    expect(p.headline).toContain("NDX");
  });
});
