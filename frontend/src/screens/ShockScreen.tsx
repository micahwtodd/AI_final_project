import { useEffect, useState } from "react";
import { api, type Review, type Shock } from "../api";
import { fmtBn, fmtMove, fmtSigned } from "../labels";
import { Meters } from "../components/Meters";
import { PixelSprite } from "../components/PixelSprite";
import { CountUp } from "../components/Fx";
import { MarketTape } from "../components/MarketTape";
import { play } from "../sound";
import { Nuke } from "../components/Nuke";

// The shock lands in two beats: first the paper and the damage (with a shake sized to the loss), then Vera
// arrives to ask for an explanation. Her box shows the four things she marks as chips that light up while
// you write, and offers a hint ladder before "I'm not sure".

const FACTORS: [string, RegExp][] = [
  ["rates", /\b(rate|rates|yield|yields|interest|duration|mismatch)\b/i],
  ["stocks", /\b(stock|stocks|equit\w*|market fell|guarantee\w*|annuit\w*|puts?)\b/i],
  ["credit", /\b(credit|spread\w*|default\w*|junk|bbb|bond losses|high-yield)\b/i],
  ["liquidity", /\b(liquidity|surrender\w*|cash|collateral|margin|forced|fire.sale)\b/i],
  ["counterparty", /\b(dealer\w*|counterpart\w*)\b/i],
];
const WHY = /\b(because|since|so|which|means|meaning|due to|as a result|therefore|longer|shorter|sensitive|so that)\b/i;
const TRADES = /\b(trade\w*|hedg\w*|swaps?|puts?|sold|sell|bought|buy|protection|nothing|should have|would have|could have|moved|added|cost us)\b/i;

function chipsFor(text: string) {
  const groups = FACTORS.filter(([, re]) => re.test(text)).length;
  return [
    { key: "main", label: "Main driver", on: groups >= 1 },
    { key: "why", label: "Why it moved surplus", on: WHY.test(text) && groups >= 1 },
    { key: "second", label: "Second factor", on: groups >= 2 },
    { key: "trades", label: "What my trades did", on: TRADES.test(text) },
  ];
}

export function ShockScreen(props: {
  shock: Shock;
  busy: boolean;
  firstTry: { review: Review; question: string } | null;
  company: string;
  gameId: string;
  onSubmit: (text: string, notSure: boolean) => void;
}) {
  const s = props.shock;
  const [text, setText] = useState("");
  const second = props.firstTry !== null;
  const [veraIn, setVeraIn] = useState(second);
  const [nukeOpen, setNukeOpen] = useState(!!s.collapsed && !second);
  const [hints, setHints] = useState<string[]>([]);
  const [hintMax, setHintMax] = useState(false);
  const breach = s.dashboard_after.status.capital === "red" || s.dashboard_after.status.liquidity === "red";
  const lossShare = s.surplus_before > 0 ? Math.abs(s.surplus_change) / s.surplus_before : 0;

  useEffect(() => {
    if (second) return;
    let shakeT = 0;
    if (!s.collapsed && s.surplus_change < 0) {  // a shake sized to the loss (the explosion has its own)
      const size = lossShare > 0.15 ? "l" : lossShare > 0.05 ? "m" : "s";
      document.body.classList.add(`shake-${size}`);
      shakeT = window.setTimeout(() => document.body.classList.remove(`shake-${size}`), 900);
    }
    const t = s.collapsed ? 0 : window.setTimeout(() => play(breach || s.surplus_change < 0 ? "alarm" : "bell"), 500);
    const v = window.setTimeout(() => setVeraIn(true), 2800);  // hold the paper, then Vera knocks
    return () => { clearTimeout(t); clearTimeout(v); clearTimeout(shakeT); document.body.classList.remove("shake-s", "shake-m", "shake-l"); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const locked = props.busy || nukeOpen;
  const chips = chipsFor(text);
  const p = s.prediction;

  async function askHint() {
    const r = await api.hint(props.gameId).catch(() => null);
    if (!r) return;
    play("click");
    setHints((h) => [...h, r.hint]);
    if (r.level >= r.max) setHintMax(true);
  }

  return (
    <section className={`shock ${s.boss ? "boss" : ""}`}>
      {nukeOpen && <Nuke company={props.company} surplus={s.surplus_after} onDone={() => setNukeOpen(false)} />}
      <MarketTape moves={s.market_moves} quarter={s.quarter} boss={!!s.boss} />
      {p && (
        <div className={`call-banner ${p.correct ? "hit" : "miss"}`}>
          {p.correct ? <>🎯 You called it: <b>{p.answer_label}</b>.</> : <>You called <b>{p.pick_label}</b>. It was <b>{p.answer_label}</b>.</>}
        </div>
      )}
      <div className="newspaper paper-in">
        {s.boss && <div className="extra-edition">EXTRA EDITION</div>}
        <div className="paper-mast">THE MARKET DAILY · Q{s.quarter} · {s.era}</div>
        <h1 className="paper-headline">{s.headline}</h1>
        <p className="paper-body">{s.narrative}</p>
        {s.real_world?.title && (
          <div className="paper-real">
            <span className="paper-real-tag">IN REAL LIFE</span> <b>{s.real_world.title}.</b> {s.real_world.text}
          </div>
        )}
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
              <div className="muted small">{fmtBn(s.surplus_before)} → {fmtBn(s.surplus_after)}</div>
            </div>
          </div>
        </div>

        {!veraIn ? (
          <div className="panel cro cro-waiting">
            <PixelSprite name="vera_neutral" size={72} title="Vera Atrisk" />
            <p className="muted">Vera is on her way over…</p>
            <button className="ghost" onClick={() => setVeraIn(true)}>Call her over now →</button>
          </div>
        ) : (
          <div className="panel cro cro-in">
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
            {hints.map((h, i) => <div key={i} className="hint-note"><b>Hint {i + 1}</b> {h}</div>)}
            <textarea rows={6} value={text} disabled={nukeOpen} onChange={(e) => setText(e.target.value)}
              placeholder={second ? "Try again: what moved most, and why did it hurt or help this company?"
                : "What moved, why it hurt or helped this company, and what your trades did."} />
            <div className="rubric-chips" aria-label="What Vera marks">
              {chips.map((c) => <span key={c.key} className={`rubric-chip ${c.on ? "on" : ""}`}>{c.on ? "●" : "○"} {c.label}</span>)}
              <span className="rubric-note">These light up when your answer touches each part. Vera decides whether it is right.</span>
            </div>
            <div className="explain-row">
              {s.sample_answer && !second && <button className="ghost" disabled={locked} onClick={() => setText(s.sample_answer!)}>Use a sample answer (demo)</button>}
              {!second && !hintMax && <button className="ghost" disabled={locked} onClick={askHint}>{hints.length ? "Bigger hint" : "Hint"}</button>}
              <button className="ghost" disabled={locked} onClick={() => props.onSubmit("", true)}>I'm not sure</button>
              <button className="gold-btn" disabled={locked || !text.trim()} onClick={() => { props.onSubmit(text, false); setText(""); }}>
                {props.busy ? <span className="spinner" aria-label="marking" /> : second ? "Submit second try" : "Submit explanation"}
              </button>
            </div>
            {hints.length > 1 && <div className="small muted">The bigger hint named the main driver, so that check counts half.</div>}
          </div>
        )}
      </div>
    </section>
  );
}
