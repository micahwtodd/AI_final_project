import { useState } from "react";
import type { Usage } from "../api";

const NAMES: Record<string, string> = { solo: "Vera (Solo)", cro: "Vera (CRO)", actuary: "Morty (Actuary)",
  portfolio_manager: "Bonnie (Portfolio Mgr)", trader: "Swap Dogg (Trader)", examiner: "Vera (Examiner)", calibration: "Seamore (Calibration)" };

export function UsageMeter(props: { gameId: string; usage: Usage; onUsage: (u: Usage) => void }) {
  const [open, setOpen] = useState(false);
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
          <div className="small muted">AI cap: ${u.budget_cap_usd.toFixed(2)} per game, fixed. When it is reached, the AI colleagues go offline and the game continues.</div>
          {u.blocked && <div className="warn small">Cap reached: the AI colleagues are offline for the rest of this game.</div>}
        </div>
      )}
    </div>
  );
}
