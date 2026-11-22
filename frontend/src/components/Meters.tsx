import type { Dashboard } from "../api";
import { Term } from "./Term";

type Meter = { key: string; term?: string; label: string; value: string; status?: string; hint: string; afterValue?: string };

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
    { key: "capital", term: "capital_ratio", label: "Capital ratio", value: a.capital, afterValue: b?.capital, status: d.status.capital, hint: "Surplus ÷ simplified capital requirement. Floor 100%. Simplified, not statutory RBC." },
    { key: "liquidity", term: "liquidity_ratio", label: "Liquidity ratio", value: a.liquidity, afterValue: b?.liquidity, status: d.status.liquidity, hint: "Cash and government bonds ÷ cash you might need in a 90-day stress. Floor 100%." },
    { key: "gap", term: "duration_gap", label: "Rate mismatch (duration gap)", value: a.gap, afterValue: b?.gap, status: d.status.duration_gap, hint: "Negative: liabilities are more rate-sensitive than assets, so falling rates hurt." },
    { key: "dv01", term: "dv01", label: "Surplus if rates fall 0.01%", value: a.dv01, afterValue: b?.dv01, hint: "Net DV01 in $ millions, after swaps." },
    { key: "equity", term: "variable_annuity_guarantee", label: "Stock-market exposure", value: a.equity, afterValue: b?.equity, hint: "Loss if stocks fell 100%: alternatives (incl. stocks) held plus unhedged guarantees." },
    { key: "cpty", term: "counterparty_risk", label: "Owed by dealers (uncollateralized)", value: a.cpty, afterValue: b?.cpty, hint: "Hedge gains a dealer owes you without collateral. Lost if the dealer fails." },
  ];
}

export function Meters(props: { dashboard: Dashboard; after?: Dashboard }) {
  return (
    <div className="meters">
      {meters(props.dashboard, props.after).map((m) => (
        <div key={m.key} className={`meter ${m.status ?? ""}`}>
          <div className="meter-label">{m.term ? <Term k={m.term}>{m.label}</Term> : m.label}</div>
          <div className="meter-value">
            {m.value}
            {m.afterValue && m.afterValue !== m.value && <span className="meter-after"> → {m.afterValue}</span>}
          </div>
          <div className="meter-hint">{m.hint}</div>
        </div>
      ))}
    </div>
  );
}
