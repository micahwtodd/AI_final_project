import type { Dashboard } from "../api";
import { Term } from "./Term";

type Gauge = { now: number; after?: number; min: number; max: number; floor?: number; amber?: number; center?: boolean };
type Meter = { key: string; term?: string; label: string; value: string; status?: string; hint: string; afterValue?: string; gauge?: Gauge };

function GaugeBar({ g }: { g: Gauge }) {
  const pct = (v: number) => `${Math.max(0, Math.min(100, (100 * (v - g.min)) / (g.max - g.min)))}%`;
  const moved = g.after !== undefined && Math.abs(g.after - g.now) > 1e-6;
  return (
    <div className={`gauge ${g.center ? "center" : ""}`} aria-hidden>
      {g.amber !== undefined && <span className="gauge-amber" style={{ left: pct(g.floor ?? g.min), width: `calc(${pct(g.amber)} - ${pct(g.floor ?? g.min)})` }} />}
      {g.floor !== undefined && <span className="gauge-red" style={{ width: pct(g.floor) }} />}
      {g.floor !== undefined && <span className="gauge-floor" style={{ left: pct(g.floor) }} />}
      {g.center && <span className="gauge-zero" style={{ left: pct(0) }} />}
      <span className={`gauge-needle ${moved ? "ghost" : ""}`} style={{ left: pct(g.now) }} />
      {moved && <span className="gauge-needle after" style={{ left: pct(g.after!) }} />}
    </div>
  );
}

function meters(d: Dashboard, after?: Dashboard): Meter[] {
  const m = (v: Dashboard) => ({
    surplus: `$${v.surplus_usd_bn.toFixed(2)}bn`,
    capital: `${v.capital_ratio_pct.toFixed(0)}%`,
    liquidity: `${v.liquidity_ratio_pct.toFixed(0)}%`,
    gap: `${v.duration_gap_years >= 0 ? "+" : ""}${v.duration_gap_years.toFixed(2)} yrs`,
    dv01: `${v.net_dv01_usd_mn >= 0 ? "+" : ""}${v.net_dv01_usd_mn.toFixed(1)}mn`,
    equity: `$${v.net_equity_exposure_usd_bn.toFixed(2)}bn`,
    fx: `$${v.fx_exposure_usd_bn.toFixed(2)}bn`,
    cpty: `$${v.counterparty_exposure_usd_bn.toFixed(2)}bn`,
  });
  const a = m(d);
  const b = after ? m(after) : undefined;
  return [
    { key: "surplus", term: "surplus", label: "Surplus (equity cushion)", value: a.surplus, afterValue: b?.surplus, hint: "Assets minus liabilities. What protects policyholders." },
    { key: "capital", term: "capital_ratio", label: "Capital ratio", value: a.capital, afterValue: b?.capital, status: d.status.capital,
      hint: "Surplus ÷ the capital a simplified regulator would require. The floor is 100%: below it, a real insurer faces regulators and rating downgrades, and here you lose 10 points (unless a pro would have breached too). Amber under 130%.",
      gauge: { now: d.capital_ratio_pct, after: after?.capital_ratio_pct, min: 0, max: 300, floor: 100, amber: 130 } },
    { key: "liquidity", term: "liquidity_ratio", label: "Liquidity ratio", value: a.liquidity, afterValue: b?.liquidity, status: d.status.liquidity,
      hint: "Cash and government bonds ÷ the cash you might need in a 90-day stress (surrenders plus collateral calls). The floor is 100%: below it you could be forced to sell other bonds at a loss, and you lose 10 points (unless a pro would have breached too). Amber under 150%.",
      gauge: { now: d.liquidity_ratio_pct, after: after?.liquidity_ratio_pct, min: 0, max: 300, floor: 100, amber: 150 } },
    { key: "gap", term: "duration_gap", label: "Rate mismatch (duration gap)", value: a.gap, afterValue: b?.gap, status: d.status.duration_gap,
      hint: "Years by which assets are more rate-sensitive than liabilities. Negative: the promises to policyholders are longer, so falling rates hurt and rising rates help. Zero means fully matched; receive-fixed swaps move it toward zero.",
      gauge: { now: d.duration_gap_years, after: after?.duration_gap_years, min: -4, max: 4, center: true } },
    { key: "dv01", term: "dv01", label: "Surplus change per 0.01% rate fall", value: a.dv01, afterValue: b?.dv01, hint: "How much surplus moves, in $ millions, if rates fall by one basis point (0.01%), after swaps. A 1% fall is 100 times this." },
    { key: "equity", term: "variable_annuity_guarantee", label: "Stock-market exposure", value: a.equity, afterValue: b?.equity, hint: "Loss if stocks fell 100%: alternatives (incl. stocks) held plus unhedged guarantees." },
    { key: "cpty", term: "counterparty_risk", label: "Owed by dealers (uncollateralized)", value: a.cpty, afterValue: b?.cpty, hint: "Hedge gains a dealer owes you without collateral. Lost if the dealer fails." },
  ];
}

export function Meters(props: { dashboard: Dashboard; after?: Dashboard }) {
  return (
    <div className="meters">
      {meters(props.dashboard, props.after).map((m) => (
        <div key={m.key} className={`meter ${m.status ?? ""}`}>
          <div className="meter-label"><Term k={m.term ?? m.key} text={m.hint}>{m.label}</Term></div>
          <div className="meter-value">
            {m.value}
            {m.afterValue && m.afterValue !== m.value && <span className="meter-after"> → {m.afterValue}</span>}
          </div>
          {m.gauge && <GaugeBar g={m.gauge} />}
        </div>
      ))}
    </div>
  );
}
