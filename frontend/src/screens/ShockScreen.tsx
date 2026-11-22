import { useEffect, useState } from "react";
import type { Review, Shock } from "../api";
import { fmtMove, fmtSigned } from "../labels";
import { Meters } from "../components/Meters";
import { PixelSprite } from "../components/PixelSprite";
import { CountUp } from "../components/Fx";
import { MarketTape } from "../components/MarketTape";
import { play } from "../sound";

export function ShockScreen(props: {
  shock: Shock;
  busy: boolean;
  firstTry: { review: Review; question: string } | null;
  onSubmit: (text: string, notSure: boolean) => void;
}) {
  const s = props.shock;
  const [text, setText] = useState("");
  const second = props.firstTry !== null;
  const breach = s.dashboard_after.status.capital === "red" || s.dashboard_after.status.liquidity === "red";
  useEffect(() => {
    if (second) return;
    const t = setTimeout(() => play(breach || s.surplus_change < 0 ? "alarm" : "bell"), 500);
    return () => clearTimeout(t);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className={`shock ${s.quarter === 4 ? "boss" : ""}`}>
      <MarketTape moves={s.market_moves} quarter={s.quarter} boss={s.quarter === 4} />
      <div className="newspaper paper-in">
        {s.quarter === 4 && <div className="extra-edition">EXTRA EDITION</div>}
        <div className="paper-mast">THE MARKET DAILY · Q{s.quarter} · {s.era}</div>
        <h1 className="paper-headline">{s.headline}</h1>
        <p className="paper-body">{s.narrative}</p>
      </div>

      <div className="shock-grid">
        <div className="panel shock-dash">
          <h3>Dashboard before → after</h3>
          <Meters dashboard={s.dashboard_before} after={s.dashboard_after} />
        </div>

        <div className="shock-mid">
          <div className="panel market-summary">
            <h3>Capital Market Summary</h3>
            <table className="table compact">
              <tbody>
                {s.market_moves.map((m) => (
                  <tr key={m.key}><td>{m.label}</td><td className="num">{fmtMove(m.value, m.unit)}</td></tr>
                ))}
              </tbody>
            </table>
            <div className={`big-change pop-late ${s.surplus_change < 0 ? "neg" : "pos"}`}>
              Surplus <CountUp value={s.surplus_change} format={(v) => fmtSigned(v)} ms={1200} />
              <div className="muted small">${s.surplus_before.toFixed(2)}bn → ${s.surplus_after.toFixed(2)}bn</div>
            </div>
          </div>
          {s.real_world?.title && (
            <div className="panel real-world">
              <h3>In real life</h3>
              <b>{s.real_world.title}</b>
              <p className="small">{s.real_world.text}</p>
            </div>
          )}
        </div>

        <div className="panel cro">
          <h3 className="cro-title">Justify your actions and explain the outcomes to Vera</h3>
          <div className="cro-head">
            <PixelSprite name={s.surplus_change < 0 ? "vera_concerned" : "vera_neutral"} size={72} title="Vera Atrisk" />
            <div className="cro-name">Vera Atrisk · Chief Risk Officer</div>
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
          <textarea rows={6} value={text} onChange={(e) => setText(e.target.value)}
            placeholder={second ? "Try again: what moved most, and why did it hurt or help this company?"
              : "What moved, why it hurt or helped this company, and what your trades did."} />
          <div className="explain-row">
            {s.sample_answer && !second && <button className="ghost" onClick={() => setText(s.sample_answer!)}>Use a sample answer (demo)</button>}
            <button className="ghost" disabled={props.busy} onClick={() => props.onSubmit("", true)}>I'm not sure</button>
            <button className="primary" disabled={props.busy || !text.trim()} onClick={() => { props.onSubmit(text, false); setText(""); }}>
              {props.busy ? <span className="spinner" aria-label="marking" /> : second ? "Submit second try" : "Submit explanation"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
