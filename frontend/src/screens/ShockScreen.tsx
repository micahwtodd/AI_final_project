import { useState } from "react";
import type { Shock } from "../api";
import { fmtMove, fmtSigned } from "../labels";
import { Meters } from "../components/Meters";

export function ShockScreen(props: { shock: Shock; busy: boolean; onSubmit: (text: string, notSure: boolean) => void }) {
  const s = props.shock;
  const [text, setText] = useState("");
  const words = text.trim().split(/\s+/).filter(Boolean).length;

  return (
    <section className="shock">
      <div className="newspaper shake">
        <div className="paper-mast">THE MARKET DAILY · Q{s.quarter} · {s.era}</div>
        <h1 className="paper-headline">{s.headline}</h1>
        <p className="paper-body">{s.narrative}</p>
      </div>

      <div className="two-col">
        <div className="panel">
          <h3>What the markets did <span className="muted small">(severity {s.severity}×, seed {s.seed})</span></h3>
          <table className="table">
            <tbody>
              {s.market_moves.map((m) => (
                <tr key={m.key}><td>{m.label}</td><td className="num">{fmtMove(m.value, m.unit)}</td></tr>
              ))}
            </tbody>
          </table>
          <div className={`big-change ${s.surplus_change < 0 ? "neg" : "pos"}`}>
            Surplus {fmtSigned(s.surplus_change)} <span className="muted small">(${s.surplus_before.toFixed(2)}bn → ${s.surplus_after.toFixed(2)}bn)</span>
          </div>
        </div>

        <div className="panel cro">
          <div className="cro-name">Dr. Amara Okafor · Chief Risk Officer</div>
          <p className="cro-question">“{s.question}”</p>
          <textarea rows={5} value={text} onChange={(e) => setText(e.target.value)}
            placeholder="Two to four sentences: what moved, why it hurt or helped this company, and what your trades did." />
          <div className="explain-row">
            <span className="small muted">{words} words {words < 15 && "(15 minimum)"}</span>
            <button className="ghost" disabled={props.busy} onClick={() => props.onSubmit("", true)}>I'm not sure</button>
            <button className="primary" disabled={props.busy || words < 15} onClick={() => props.onSubmit(text, false)}>
              Submit explanation
            </button>
          </div>
          <p className="small muted">The breakdown by cause stays hidden until you explain.</p>
        </div>
      </div>

      <div className="panel">
        <h3>Dashboard before → after the shock</h3>
        <Meters dashboard={s.dashboard_before} after={s.dashboard_after} />
      </div>
    </section>
  );
}
