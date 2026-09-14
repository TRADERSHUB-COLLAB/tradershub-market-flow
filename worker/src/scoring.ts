/**
 * Regime scoring and driver ranking for the Market Pulse.
 *
 * Direct TypeScript port of `app/core/scoring.py`. Behaviour is preserved
 * so the Python offline harness (validation/replay.py) remains a valid
 * reference implementation. Any change here should also land in the
 * Python engine, or be gated behind an explicit version bump.
 */

export type AssetClass =
  | "equity"
  | "fx"
  | "rates"
  | "commodity"
  | "crypto";

export type Role = "risk" | "safe_haven" | "usd" | "yield" | "commodity";

export type Regime = "risk_on" | "risk_off" | "mixed" | "consolidation";

export type Session = "asia" | "europe" | "us";

export interface AssetQuote {
  symbol: string;
  asset_class: AssetClass;
  change_pct: number; // e.g. 0.85 = +0.85%
  role: Role;
}

export interface MarketSnapshot {
  session: Session;
  trade_date: string; // ISO date YYYY-MM-DD
  quotes: AssetQuote[];
}

export interface Driver {
  symbol: string;
  asset_class: string;
  change_pct: number;
  role: string;
  weight: number;
}

export interface Confirmation {
  name: string;
  passed: boolean;
  detail: string;
}

export interface Invalidation {
  name: string;
  condition: string;
}

export interface MarketPulse {
  session: Session;
  trade_date: string;
  regime: Regime;
  score: number; // [-1, 1]
  headline: string;
  drivers: Driver[];
  confirmations: Confirmation[];
  invalidations: Invalidation[];
}

// Role -> polarity applied to change_pct when contributing to the risk score.
const ROLE_POLARITY: Record<Role, number> = {
  risk: 1.0,
  safe_haven: -1.0,
  usd: -1.0,
  yield: -0.5,
  commodity: 0.5,
};

const MIN_ACTIVITY = 0.25;

function regimeFromScore(score: number): Regime {
  if (score >= 0.35) return "risk_on";
  if (score <= -0.35) return "risk_off";
  if (Math.abs(score) < 0.1) return "consolidation";
  return "mixed";
}

function headline(regime: Regime, score: number, top: AssetQuote | null): string {
  const pct = `${(score * 100).toFixed(0).replace(/^(?!-)/, "+")}`;
  if (!top) {
    const label = regime.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
    return `${label} regime (score ${pct}).`;
  }
  const lead = `${top.symbol} ${top.change_pct >= 0 ? "+" : ""}${top.change_pct.toFixed(2)}%`;
  switch (regime) {
    case "risk_on":
      return `Risk-on tone with ${lead} leading (score ${pct}).`;
    case "risk_off":
      return `Defensive tone with ${lead} leading (score ${pct}).`;
    case "consolidation":
      return `Range / consolidation, ${lead} in focus (score ${pct}).`;
    default:
      return `Mixed cross-asset picture, ${lead} in focus (score ${pct}).`;
  }
}

function round(n: number, dp: number): number {
  const f = 10 ** dp;
  return Math.round(n * f) / f;
}

export function computePulse(snapshot: MarketSnapshot): MarketPulse {
  const quotes = snapshot.quotes;

  const contribs: Array<[AssetQuote, number]> = quotes.map((q) => [
    q,
    ROLE_POLARITY[q.role] * q.change_pct,
  ]);
  const totalAbs = quotes.reduce((s, q) => s + Math.abs(q.change_pct), 0);
  const denom = totalAbs > 0 ? totalAbs : 1;
  const rawScore = contribs.reduce((s, [, c]) => s + c, 0);
  let score = Math.max(-1, Math.min(1, rawScore / denom));

  // Damp quiet-tape noise so a flat market resolves to consolidation.
  if (totalAbs < MIN_ACTIVITY) {
    score *= totalAbs / MIN_ACTIVITY;
  }

  const ranked = [...contribs].sort(
    (a, b) => Math.abs(b[1]) - Math.abs(a[1]),
  );
  const topQuote = ranked.length > 0 ? ranked[0][0] : null;

  const drivers: Driver[] = ranked.slice(0, 5).map(([q, contrib]) => ({
    symbol: q.symbol,
    asset_class: q.asset_class,
    change_pct: q.change_pct,
    role: q.role,
    weight: round(Math.abs(contrib) / denom, 4),
  }));

  const regime = regimeFromScore(score);

  const equities = quotes.filter((q) => q.asset_class === "equity");
  const usd = quotes.find((q) => q.asset_class === "fx" && q.role === "usd");

  const confirmations: Confirmation[] = [];
  if (equities.length > 0) {
    const up = equities.filter((q) => q.change_pct > 0).length;
    confirmations.push({
      name: "equity_breadth",
      passed:
        (regime === "risk_on" && up >= equities.length / 2) ||
        (regime === "risk_off" && up <= equities.length / 2) ||
        regime === "mixed" ||
        regime === "consolidation",
      detail: `${up}/${equities.length} tracked equity indices moved in the direction of the regime.`,
    });
  }
  if (usd) {
    confirmations.push({
      name: "usd_alignment",
      passed:
        (regime === "risk_on" && usd.change_pct <= 0) ||
        (regime === "risk_off" && usd.change_pct >= 0) ||
        regime === "mixed" ||
        regime === "consolidation",
      detail: `USD proxy ${usd.symbol} at ${usd.change_pct >= 0 ? "+" : ""}${usd.change_pct.toFixed(2)}%.`,
    });
  }

  const invalidations: Invalidation[] = [
    {
      name: "regime_flip",
      condition:
        "Score crosses zero and holds for more than 30 minutes with equity breadth reversing.",
    },
    {
      name: "driver_fade",
      condition: `Top driver ${topQuote ? topQuote.symbol : "n/a"} gives back more than 50% of its session move.`,
    },
  ];

  return {
    session: snapshot.session,
    trade_date: snapshot.trade_date,
    regime,
    score: round(score, 4),
    headline: headline(regime, score, topQuote),
    drivers,
    confirmations,
    invalidations,
  };
}
