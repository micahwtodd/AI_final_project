import { useEffect, useRef, useState } from "react";
import { api, type Company, type Dashboard, type GameInput } from "../api";
import { BalanceSheetPanel } from "../components/BalanceSheet";
import { CompanyLogo } from "../components/CompanyLogo";
import { Dossier } from "../components/Dossier";
import { InputsEditor } from "../components/InputsEditor";

export function CompanySelect(props: { companies: Company[]; busy: boolean; onStart: (ticker: string, seed: number, overrides: Record<string, number>) => void;
  initialPick?: { ticker: string; seed: number } | null; onIntro?: () => void; onDemo: () => void }) {
  const [picked, setPicked] = useState<string | null>(props.initialPick?.ticker ?? null);
  const [seed, setSeed] = useState(props.initialPick?.seed ?? 409);
  const chosen = props.companies.find((c) => c.ticker === picked);
  const [overrides, setOverrides] = useState<Record<string, number>>({});
  const [preview, setPreview] = useState<{ dashboard: Dashboard; inputs: GameInput[] } | null>(null);
  const [inputErr, setInputErr] = useState<string | null>(null);
  const panel = useRef<HTMLDivElement>(null);

  // a new company starts from Seamore's values; scroll its balance sheet into view
  useEffect(() => {
    setOverrides({});
    setPreview(null);
    setInputErr(null);
    if (picked) setTimeout(() => panel.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
  }, [picked]);

  // live preview of edited inputs (debounced)
  useEffect(() => {
    if (!picked) return;
    if (Object.keys(overrides).length === 0) { setPreview(null); setInputErr(null); return; }
    const t = setTimeout(() => {
      api.previewCompany(picked, overrides)
        .then((r) => { setPreview(r); setInputErr(null); })
        .catch((e) => setInputErr(e instanceof Error ? e.message : String(e)));
    }, 300);
    return () => clearTimeout(t);
  }, [picked, overrides]);
  const edited = Object.keys(overrides).length;

  return (
    <section className="select">
      <div className="hero hero-game">
        <div className="hero-top">
          <div>
            <div className="hero-kicker">Six real insurers · real balance sheets · one brutal year</div>
            <h1>Pick your insurer.</h1>
          </div>
          <div className="hero-actions">
            <button className="demo-btn" disabled={props.busy} onClick={props.onDemo} title="Jackson Financial with sample answers for every step">▶ Demo mode</button>
            {props.onIntro && <button className="link hero-link" onClick={props.onIntro}>↺ Replay intro</button>}
          </div>
        </div>
        <ol className="rules">
          <li><span className="rule-n">1</span><b>Read the wire.</b> A hint of what's coming. Maybe.</li>
          <li><span className="rule-n">2</span><b>Make your moves.</b> Hedge, de-risk, hold cash. Nothing's free.</li>
          <li><span className="rule-n">3</span><b>Take the hit.</b> Stay above the capital and cash floors.</li>
          <li><span className="rule-n">4</span><b>Explain it to Vera.</b> Get it right, score points.</li>
        </ol>
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
          </button>
        ))}
      </div>

      {chosen && (
        <div className="panel dossier" ref={panel} key={chosen.ticker}>
          <div className="dossier-head">
            <CompanyLogo ticker={chosen.ticker} name={chosen.name} />
            <h2>
              {chosen.name} <span className="muted">({chosen.ticker}) · general account balance sheet, FY{chosen.fiscal_year}</span>
            </h2>
          </div>
          <BalanceSheetPanel dashboard={preview?.dashboard ?? chosen.dashboard} />
          {edited > 0 && <div className="custom-flag small">Using your edited inputs ({edited}). Seamore's figures are under Advanced options.</div>}
          <p className="small muted">
            Excludes separate account assets, but includes general account guarantees written on them.
            Equity is shown excluding unrealized bond gains and losses (AOCI).
          </p>
          <div className="start-row approve-row">
            <button className="gold-btn approve-btn" disabled={props.busy || !!inputErr} onClick={() => props.onStart(chosen.ticker, seed, overrides)}>
              {props.busy ? "Starting…" : `Approve dossier and run ${chosen.name} →`}
            </button>
          </div>
          <details className="advanced">
            <summary>Advanced options <span className="muted small">· seed, edit inputs, Seamore's sources</span></summary>
            <div className="seed-row">
              <label>
                Seed{" "}
                <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value) || 0)} />
              </label>
              <span className="small muted">Same seed, same market shocks, so runs can be compared.</span>
            </div>
            <InputsEditor inputs={chosen.inputs} overrides={overrides} onChange={setOverrides} error={inputErr} />
            <Dossier company={chosen} />
          </details>
        </div>
      )}
    </section>
  );
}
