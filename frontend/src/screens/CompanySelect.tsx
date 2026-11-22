import { useState } from "react";
import type { Company } from "../api";
import { ASSET_LABELS, LIABILITY_LABELS } from "../labels";
import { MixBar } from "../components/MixBar";

export function CompanySelect(props: { companies: Company[]; busy: boolean; onStart: (ticker: string, seed: number) => void }) {
  const [picked, setPicked] = useState<string | null>(null);
  const [seed, setSeed] = useState(409);
  const chosen = props.companies.find((c) => c.ticker === picked);

  return (
    <section className="select">
      <div className="hero">
        <h1>Run a life insurer through a year of market stress</h1>
        <p>
          Pick a real, publicly traded insurer. Its balance sheet comes from its latest 10-K filing with the SEC. Each
          quarter you read the news, decide how to protect the company, and sign a trade ticket. Then the market moves.
        </p>
      </div>

      <div className="company-grid">
        {props.companies.map((c) => (
          <button
            key={c.ticker}
            className={`company-card ${picked === c.ticker ? "picked" : ""}`}
            onClick={() => setPicked(c.ticker)}
          >
            <div className="ticker">{c.ticker}</div>
            <div className="name">{c.name}</div>
            <div className="stats">
              <span>Invested assets ${c.invested_assets_usd_bn.toFixed(0)}bn</span>
              <span>Surplus ${c.surplus_usd_bn.toFixed(1)}bn</span>
              <span>Cushion {(100 * c.equity_to_assets).toFixed(1)}% of assets</span>
            </div>
            <div className="muted small">FY{c.fiscal_year} 10-K</div>
          </button>
        ))}
      </div>

      {chosen && (
        <div className="panel dossier">
          <h2>
            {chosen.name} <span className="muted">({chosen.ticker})</span>
          </h2>
          <div className="two-col">
            <div>
              <h3>What it owns (assets)</h3>
              <MixBar mix={chosen.asset_mix} labels={ASSET_LABELS} />
            </div>
            <div>
              <h3>What it owes (liabilities)</h3>
              <MixBar mix={chosen.liability_mix} labels={LIABILITY_LABELS} />
              <p className="small muted">
                Policies with stock-market guarantees: ${chosen.guarantee_exposure_usd_bn.toFixed(0)}bn of account value
                (separate accounts ${chosen.separate_account_assets_usd_bn.toFixed(0)}bn).
              </p>
            </div>
          </div>
          <div className="start-row">
            <label>
              Seed{" "}
              <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value) || 0)} />
            </label>
            <span className="small muted">Same seed, same market shocks: runs can be compared.</span>
            <button className="primary" disabled={props.busy} onClick={() => props.onStart(chosen.ticker, seed)}>
              {props.busy ? "Starting…" : `Start with ${chosen.ticker}`}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
