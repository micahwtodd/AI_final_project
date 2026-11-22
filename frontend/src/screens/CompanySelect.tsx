import { useState } from "react";
import type { Company } from "../api";
import { BalanceSheetPanel } from "../components/BalanceSheet";
import { CompanyLogo } from "../components/CompanyLogo";
import { Dossier } from "../components/Dossier";

export function CompanySelect(props: { companies: Company[]; busy: boolean; onStart: (ticker: string, seed: number) => void; onDemo: () => void }) {
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
        <div className="demo-row">
          <button className="primary demo-btn" disabled={props.busy} onClick={props.onDemo}>▶ Demo mode</button>
          <span className="small muted">One click: Jackson Financial, seed 409, the full team, with sample answers so you can see every feature without knowing insurance.</span>
        </div>
      </div>

      <div className="company-grid">
        {props.companies.map((c) => (
          <button
            key={c.ticker}
            className={`company-card ${picked === c.ticker ? "picked" : ""}`}
            onClick={() => setPicked(c.ticker)}
            aria-pressed={picked === c.ticker}
          >
            <div className="company-head">
              <CompanyLogo ticker={c.ticker} name={c.name} />
              <div>
                <div className="name">{c.name}</div>
                <div className="ticker">{c.ticker}</div>
              </div>
            </div>
            <div className="stats">
              <span>Invested assets <b>${c.invested_assets_usd_bn.toFixed(0)}bn</b></span>
              <span>Surplus <b>${c.surplus_usd_bn.toFixed(1)}bn</b></span>
              <span>Cushion <b>{(100 * c.equity_to_assets).toFixed(1)}%</b> of assets</span>
            </div>
            <div className="muted small">FY{c.fiscal_year} 10-K</div>
          </button>
        ))}
      </div>

      {chosen && (
        <div className="panel dossier">
          <div className="dossier-head">
            <CompanyLogo ticker={chosen.ticker} name={chosen.name} />
            <h2>
              {chosen.name} <span className="muted">({chosen.ticker}) · general account balance sheet, FY{chosen.fiscal_year}</span>
            </h2>
          </div>
          <BalanceSheetPanel dashboard={chosen.dashboard} />
          <p className="small muted">
            Separate-account assets (${chosen.separate_account_assets_usd_bn.toFixed(0)}bn) belong to policyholders and are
            left out, except the stock-market guarantees written on them: ${chosen.guarantee_exposure_usd_bn.toFixed(0)}bn of
            account value carries a guarantee. Equity is shown excluding unrealized bond gains and losses (AOCI).
          </p>
          <Dossier company={chosen} />
          <div className="start-row">
            <label>
              Seed{" "}
              <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value) || 0)} />
            </label>
            <span className="small muted">Same seed, same market shocks: runs can be compared.</span>
            <button className="primary" disabled={props.busy} onClick={() => props.onStart(chosen.ticker, seed)}>
              {props.busy ? "Starting…" : `Approve dossier and start with ${chosen.ticker}`}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
