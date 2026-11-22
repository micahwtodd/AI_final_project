import { useState } from "react";
import type { Review, Shock } from "../api";
import { fmtMove, fmtSigned } from "../labels";
import { Meters } from "../components/Meters";
import { PixelSprite } from "../components/PixelSprite";

export function ShockScreen(props: {
  shock: Shock;
  busy: boolean;
  firstTry: { review: Review; question: string } | null;
  onSubmit: (text: string, notSure: boolean) => void;
}) {
  const s = props.shock;
  const [text, setText] = useState("");
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  const second = props.firstTry !== null;

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
          <div className="cro-head">
            <PixelSprite name={s.surplus_change < 0 ? "amara_concerned" : "amara_neutral"} size={72} title="Dr. Amara Okafor" />
            <div className="cro-name">Dr. Amara Okafor · Chief Risk Officer</div>
          </div>
          <p className="cro-question">“{s.question}”</p>
          {second && (
            <div className="first-try">
              <div className="small muted">Your first answer:</div>
              <p className="cro-feedback">{props.firstTry!.review.reply_text}</p>
              {props.firstTry!.review.instruction_attempt && (
                <div className="flag small">⚑ Your answer tried to instruct the grader. Only the finance content is marked.</div>
              )}
              <p className="cro-question">“{props.firstTry!.question}”</p>
              <div className="small muted">Second try: checks you earn now count half.</div>
            </div>
          )}
          <textarea rows={5} value={text} onChange={(e) => setText(e.target.value)}
            placeholder={second ? "Try again: what moved most, and why did it hurt or help this company?"
              : "Two to four sentences: what moved, why it hurt or helped this company, and what your trades did."} />
          <div className="explain-row">
            <span className="small muted">{words} words {words < 15 && "(15 minimum)"}</span>
            {s.sample_answer && !second && <button className="ghost" onClick={() => setText(s.sample_answer!)}>Use a sample answer (demo)</button>}
            <button className="ghost" disabled={props.busy} onClick={() => props.onSubmit("", true)}>I'm not sure</button>
            <button className="primary" disabled={props.busy || words < 15} onClick={() => { props.onSubmit(text, false); setText(""); }}>
              {props.busy ? <span className="spinner" aria-label="marking" /> : second ? "Submit second try" : "Submit explanation"}
            </button>
          </div>
          <p className="small muted">The breakdown by cause stays hidden until you explain. Amara marks four things: the main driver, why it moved surplus, the second factor, and what your trades did or could have done.</p>
        </div>
      </div>

      <div className="panel">
        <h3>Dashboard before → after the shock</h3>
        <Meters dashboard={s.dashboard_before} after={s.dashboard_after} />
      </div>
    </section>
  );
}
