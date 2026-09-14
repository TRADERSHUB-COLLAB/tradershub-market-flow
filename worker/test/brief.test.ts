import { describe, expect, it } from "vitest";
import { toBrief } from "../src/brief";
import { computePulse, type AssetQuote } from "../src/scoring";

const now = new Date("2026-09-14T05:00:00.000Z");

function pulse(quotes: AssetQuote[]) {
  return computePulse({ session: "us", trade_date: "2026-09-14", quotes });
}

describe("toBrief", () => {
  it("renders a risk_on brief with proper prefix and score display", () => {
    const p = pulse([
      { symbol: "SPX", asset_class: "equity", change_pct: 1.2, role: "risk" },
      { symbol: "NDX", asset_class: "equity", change_pct: 1.5, role: "risk" },
      { symbol: "DXY", asset_class: "fx",     change_pct: -0.4, role: "usd" },
    ]);
    const b = toBrief(p, now);
    expect(b.regime.tag).toBe("risk_on");
    expect(b.regime.label).toBe("Risk-on");
    expect(b.regime.score_display.startsWith("+")).toBe(true);
    expect(b.headline).toContain("Risk-on");
    expect(b.drivers.length).toBeGreaterThan(0);
    expect(b.drivers[0].move_display).toMatch(/^\+\d/);
    expect(b.drivers[0].direction).toBe("up");
    expect(b.disclaimer).toContain("Not a signal");
    expect(b.confirms.length).toBeGreaterThan(0);
    expect(b.invalidates.length).toBe(2);
  });

  it("uses a Unicode minus sign for negative moves", () => {
    const p = pulse([
      { symbol: "SPX", asset_class: "equity", change_pct: -1.4, role: "risk" },
      { symbol: "DXY", asset_class: "fx",     change_pct: 0.5, role: "usd" },
    ]);
    const b = toBrief(p, now);
    expect(b.regime.score_display.startsWith("\u2212")).toBe(true);
    const spx = b.drivers.find((d) => d.symbol === "SPX")!;
    expect(spx.move_display.startsWith("\u2212")).toBe(true);
    expect(spx.direction).toBe("down");
  });

  it("caps drivers at 4", () => {
    const many: AssetQuote[] = [
      "A", "B", "C", "D", "E", "F", "G",
    ].map((s) => ({ symbol: s, asset_class: "equity", change_pct: 1.1, role: "risk" }));
    const b = toBrief(pulse(many), now);
    expect(b.drivers.length).toBe(4);
  });
});
