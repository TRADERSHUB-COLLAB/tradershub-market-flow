/**
 * Turn a MarketPulse into the page-ready "brief" shape the landing page
 * reads. The engine is honest — no invented facts. Every string here is
 * derived from the pulse or asset metadata. The prose stays deliberately
 * short and repeatable; the "voice" lives in the source data, not in this
 * template.
 */
import type { Driver, MarketPulse } from "./scoring";

export interface Brief {
  as_of: string; // ISO datetime
  session: string;
  trade_date: string;
  regime: {
    tag: "risk_on" | "risk_off" | "mixed" | "consolidation";
    label: string; // "Risk-on", "Risk-off", "Mixed", "Consolidation"
    score: number;
    score_display: string; // "+0.42" / "−0.18"
  };
  headline: string;
  lede: string;
  drivers: Array<{
    symbol: string;
    move_display: string; // "+1.42%"
    direction: "up" | "down" | "flat";
    note: string;
  }>;
  confirms: Array<{ text: string; passed: boolean }>;
  invalidates: string[];
  disclaimer: string;
}

const REGIME_LABEL: Record<string, string> = {
  risk_on: "Risk-on",
  risk_off: "Risk-off",
  mixed: "Mixed",
  consolidation: "Consolidation",
};

const DISCLAIMER =
  "A daily read of the whole tape. Not a signal. Not advice. Written to help you read the market before you trade it.";

// One-liner explanations per symbol/role — kept dry and factual.
function driverNote(d: Driver): string {
  const dir = d.change_pct > 0 ? "up" : d.change_pct < 0 ? "down" : "flat";
  switch (d.symbol) {
    case "SPX":    return `S&P 500 futures ${dir} — broad-market tone.`;
    case "NDX":    return `Nasdaq 100 ${dir} — tech / growth leadership.`;
    case "DAX":    return `DAX ${dir} — European risk appetite read.`;
    case "HSI":    return `Hang Seng ${dir} — Asia session hand-off.`;
    case "DXY":    return `Dollar index ${dir === "up" ? "firmer" : dir === "down" ? "softer" : "flat"} against G10.`;
    case "USDJPY": return `USDJPY ${dir} — classic risk barometer.`;
    case "XAUUSD": return `Gold ${dir === "up" ? "bid" : dir === "down" ? "offered" : "flat"} — real-yield signal.`;
    case "CL":     return `Crude ${dir} — growth / geopolitics read.`;
    case "US10Y":  return `10Y yield ${dir === "up" ? "rising" : dir === "down" ? "easing" : "flat"} — rates repricing.`;
    case "BTCUSD": return `Bitcoin ${dir} — speculative-risk pulse.`;
    default:       return `${d.symbol} ${dir}.`;
  }
}

function pct(n: number, dp = 2): string {
  const s = n.toFixed(dp);
  if (n > 0) return `+${s}%`;
  if (n < 0) return `\u2212${Math.abs(n).toFixed(dp)}%`; // Unicode minus
  return `0.00%`;
}

function scoreDisplay(n: number): string {
  const s = n.toFixed(2);
  if (n > 0) return `+${s}`;
  if (n < 0) return `\u2212${Math.abs(n).toFixed(2)}`;
  return "0.00";
}

function ledeFor(pulse: MarketPulse): string {
  const [top] = pulse.drivers;
  if (!top) {
    return `A quiet tape across the tracked instruments. Score sits near zero; no strong regime signal.`;
  }
  const dir = top.change_pct > 0 ? "leading higher" : "leading lower";
  switch (pulse.regime) {
    case "risk_on":
      return `Risk assets are bid with ${top.symbol} ${dir}. Cross-asset picture supports the tone while the drivers hold their move.`;
    case "risk_off":
      return `Defensive tone across the tape, with ${top.symbol} ${dir}. Safe-haven bid and firmer dollar consistent with the read.`;
    case "consolidation":
      return `Range conditions across the tape. ${top.symbol} is the only meaningful mover, but breadth is thin.`;
    default:
      return `Mixed cross-asset picture — ${top.symbol} ${dir} without confirmation from the rest of the tape.`;
  }
}

export function toBrief(pulse: MarketPulse, asOf: Date = new Date()): Brief {
  return {
    as_of: asOf.toISOString(),
    session: pulse.session,
    trade_date: pulse.trade_date,
    regime: {
      tag: pulse.regime,
      label: REGIME_LABEL[pulse.regime] ?? pulse.regime,
      score: pulse.score,
      score_display: scoreDisplay(pulse.score),
    },
    headline: pulse.headline,
    lede: ledeFor(pulse),
    drivers: pulse.drivers.slice(0, 4).map((d) => ({
      symbol: d.symbol,
      move_display: pct(d.change_pct),
      direction: d.change_pct > 0 ? "up" : d.change_pct < 0 ? "down" : "flat",
      note: driverNote(d),
    })),
    confirms: pulse.confirmations.map((c) => ({ text: c.detail, passed: c.passed })),
    invalidates: pulse.invalidations.map((i) => i.condition),
    disclaimer: DISCLAIMER,
  };
}
