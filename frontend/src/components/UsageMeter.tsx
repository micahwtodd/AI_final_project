import { useState } from "react";
import { api, type Usage } from "../api";

const NAMES: Record<string, string> = { solo: "Vera (Solo)", cro: "Vera (CRO)", actuary: "Morty (Actuary)",
  portfolio_manager: "Bonnie (Portfolio Mgr)", trader: "Swap Dogg (Trader)", examiner: "Vera (Examiner)", calibration: "Seamore (Calibration)" };

export function UsageMeter(props: { gameId: string; usage: Usage; onUsage: (u: Usage) => void }) {
  const [open, setOpen] = useState(false);
  const [cap, setCap] = useState(String(props.usage.budget_cap_usd));
  const u = props.usage;
  const total = u.tokens.input + u.tokens.output;
  const pct = Math.min(100, (100 * u.spend_usd) / Math.max(u.budget_cap_usd, 1e-9));

  return (
    <div className="meter-wrap">
      <button className={`pill usage-pill ${u.blocked ? "blocked" : ""}`} onClick={() => setOpen(!open)} title="AI usage this session">
        {total.toLocaleString()} tokens · ${u.spend_usd.toFixed(4)}
        <span className="budget-bar"><span style={{ width: `${pct}%` }} /></span>
        cap ${u.budget_cap_usd < 0.01 ? u.budget_cap_usd.toFixed(4) : u.budget_cap_usd.toFixed(2)}
      </button>
      {open && (
        <div className="usage-pop">
          <h3>AI usage this session</h3>
          <table className="table small">
            <thead><tr><th>Agent</th><th>Calls</th><th>Input</th><th>Cached</th><th>Output</th><th>Cost</th></tr></thead>
            <tbody>
              {Object.entries(u.by_agent).map(([k, a]) => (
                <tr key={k}><td>{NAMES[k] ?? k}</td><td>{a.requests}</td><td>{a.input.toLocaleString()}</td><td>{a.cached.toLocaleString()}</td><td>{a.output.toLocaleString()}</td><td>${a.cost_usd.toFixed(5)}</td></tr>
              ))}
              <tr className="total"><td>Total</td><td>{u.tokens.requests}</td><td>{u.tokens.input.toLocaleString()}</td><td>{u.tokens.cached.toLocaleString()}</td><td>{u.tokens.output.toLocaleString()}</td><td>${u.spend_usd.toFixed(5)}</td></tr>
            </tbody>
          </table>
          <div className="small muted">Token counts are reported by the API. Prices: gpt-6-luna $0.10 input, $0.01 cached, $0.50 output per million tokens.</div>
          <form className="cap-row" onSubmit={async (e) => {
            e.preventDefault();
            const v = Number(cap);
            if (Number.isFinite(v) && v >= 0) props.onUsage(await api.setBudget(props.gameId, v));
          }}>
            <label>Budget cap $ <input type="number" step="any" min="0" max="5" value={cap} onChange={(e) => setCap(e.target.value)} /></label>
            <button className="primary">Set cap</button>
          </form>
          {u.blocked && <div className="warn small">Cap reached: questions are blocked until the cap is raised.</div>}
        </div>
      )}
    </div>
  );
}
