import { useEffect, useRef, useState } from "react";
import { WhatIfPanel } from "../components/WhatIf";
import type { Action, Reveal, Shock } from "../api";
import { LEVERS, LESSON_ICON, type LeverKey } from "../labels";
import { PixelSprite } from "../components/PixelSprite";
import { Confetti, CountUp } from "../components/Fx";
import { BadgeUnlocks } from "../components/Badges";
import { play } from "../sound";

// The quarter's results, told in four beats: Vera's trade feedback, the scoreboard, how a pro would
// have traded, and the lesson card. The full numbers sit in a collapsed breakdown at the bottom.

type Row = { key?: string; label: string; value: number; mark?: "yes" | "no"; boom?: boolean };

function Bars(props: { rows: Row[]; race?: boolean }) {
  const max = Math.max(0.01, ...props.rows.map((r) => Math.abs(r.value)));
  return (
    <div className={`bars ${props.race ? "race" : ""}`}>
      {props.rows.map((r, i) => (
        <div className="bar-row" key={r.label}>
          <div className="bar-label">
            {r.mark && <span className={`tick ${r.mark}`} title={r.mark === "yes" ? "You named this" : "You did not name this"}>{r.mark === "yes" ? "✓" : "✗"}</span>}
            {r.label}{r.boom && <span className="boom-tag">💥 COLLAPSED</span>}
          </div>
          <div className="bar-track">
            <div className="bar-mid" />
            <div className={`bar ${r.value < 0 ? "neg" : "pos"}`}
              style={{ width: `${(50 * Math.abs(r.value)) / max}%`, [r.value < 0 ? "right" : "left"]: "50%", animationDelay: props.race ? `${0.15 + i * 0.35}s` : undefined }} />
          </div>
          <div className={`bar-value ${r.value < 0 ? "neg" : "pos"}`}>{r.value >= 0 ? "+" : "−"}{Math.abs(r.value).toFixed(2)}bn</div>
        </div>
      ))}
    </div>
  );
}

const fmtGain = (g: number | undefined) => (g === undefined || Math.abs(g) < 0.005 ? "" : `${g > 0 ? "+" : "−"}$${Math.abs(g).toFixed(2)}bn`);

/** One row per lever: your setting, the pro's, and what matching the pro on that lever alone would have added. */
function ProTable(props: { you: Partial<Action>; pro: Partial<Action>; gains: Record<string, number> }) {
  const { you, pro, gains } = props;
  const num = (v: number | undefined) => { const x = v ?? 0; return Number.isInteger(x) ? String(x) : x.toFixed(1); };
  const rows: { key: string; label: string; y: string; p: string; track?: { you: number; pro: number } }[] = (Object.keys(LEVERS) as LeverKey[]).map((k) => {
    const L = LEVERS[k];
    const at = (v: number | undefined) => (100 * ((v ?? 0) - L.min)) / (L.max - L.min);
    return { key: k, label: L.label, y: `${num(you[k])}${L.unit}`, p: `${num(pro[k])}${L.unit}`, track: { you: at(you[k]), pro: at(pro[k]) } };
  });
  rows.push({ key: "collateralized", label: "Daily collateral", y: you.collateralized ? "On" : "Off", p: pro.collateralized ? "On" : "Off" });
  rows.push({ key: "dealers", label: "Dealers", y: String(you.dealers ?? 1), p: String(pro.dealers ?? 1) });
  const best = Object.entries(gains).sort((a, b) => b[1] - a[1])[0]?.[0];
  return (
    <table className="table ticket-table">
      <thead><tr><th></th><th>You</th><th>What a pro would do</th><th>If you'd matched the pro</th></tr></thead>
      <tbody>
        {rows.map((r) => {
          const g = gains[r.key];
          return (
            <tr key={r.key} className={`${r.y !== r.p ? "differs" : ""} ${r.key === best && g > 0.005 ? "best" : ""}`}>
              <td>
                {r.label}
                {r.track && (
                  <div className="ghost-track" aria-hidden>
                    <span className="gt-pro" style={{ left: `${r.track.pro}%` }} />
                    <span className="gt-you" style={{ left: `${r.track.you}%` }} />
                    {r.y !== r.p && <span className="gt-ghost" style={{ ["--from" as string]: `${r.track.you}%`, ["--to" as string]: `${r.track.pro}%` }} />}
                  </div>
                )}
              </td><td>{r.y}</td><td>{r.p}</td>
              <td className={g > 0.005 ? "gain pos" : g < -0.005 ? "gain neg" : "gain"}>{fmtGain(g)}{r.key === best && g > 0.005 && " ⭐"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

const CHECK_LABELS: Record<string, string> = {
  main_driver: "Named the main driver",
  mechanism: "Explained why it moved surplus",
  second_factor: "Named the second factor",
  improvement: "Said what your trades did or could have done",
};

const SHIELD_LABEL: Record<string, string> = {
  rate_hedge_pct: "Rate protection (swaps)", credit_shift_pct: "Risky bonds moved to government bonds",
  equity_hedge_pct: "Stock-market insurance (puts)", cash_buffer_pct: "Cash on hand", counterparty: "Collateral and dealers",
};

const starsFor = (score: number) => (score >= 90 ? 3 : score >= 60 ? 2 : score >= 30 ? 1 : 0);
const BEATS = ["Vera's feedback", "Scoreboard", "How a pro traded", "Lesson card"];

export function RevealScreen(props: { reveal: Reveal; shock: Shock; onNext: () => void }) {
  const r = props.reveal;
  const [beat, setBeat] = useState(0);
  const refs = useRef<(HTMLDivElement | null)[]>([]);
  const checks = r.review?.checks;
  const u = r.understanding;
  const stars = starsFor(r.quarter_score);
  const collapsed = r.collapsed?.you;

  useEffect(() => {  // Vera reacts out loud
    const t = window.setTimeout(() => play((u?.points ?? 0) >= 75 ? "bell" : (u?.points ?? 0) >= 40 ? "click" : "whoosh"), 600);
    return () => clearTimeout(t);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (beat === 0) return;
    refs.current[beat]?.scrollIntoView({ behavior: "smooth", block: "start" });
    if (beat === 1 && !collapsed) [0, 1, 2].forEach((i) => { if (i < stars) setTimeout(() => play("stamp"), 900 + i * 280); });
  }, [beat]); // eslint-disable-line react-hooks/exhaustive-deps

  const markFor = (key: string): Row["mark"] => {
    if (!checks || r.not_sure) return undefined;
    if (key === r.main_driver) return checks.main_driver ? "yes" : "no";
    if (key === r.second_factor) return checks.second_factor ? "yes" : "no";
    return undefined;
  };
  const causes: Row[] = r.attribution
    .filter((a) => Math.abs(a.value) >= 0.005)
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .map((a) => ({ key: a.key, label: a.label, value: a.value, mark: markFor(a.key) }));
  const next = (label: string) => (
    <div className="beat-next"><button className="ghost beat-btn" onClick={() => setBeat(beat + 1)}>{label} ↓</button></div>
  );

  return (
    <section className="reveal">
      {!collapsed && ((u?.points ?? 0) >= 75 || r.quarter_score >= 75) && <Confetti />}
      <BadgeUnlocks badges={r.badges_new ?? []} />
      {collapsed && <div className="collapse-banner">💥 {r.view.company.toUpperCase()} HAS COLLAPSED · GAME OVER 💥</div>}

      <ol className="beat-dots" aria-label="Results steps">
        {BEATS.map((b, i) => (
          <li key={b} className={i <= beat ? "on" : ""}>
            <button className="beat-dot" disabled={i > beat} onClick={() => refs.current[i]?.scrollIntoView({ behavior: "smooth", block: "start" })}>{i + 1}</button>
            <span>{b}</span>
          </li>
        ))}
      </ol>

      {/* Beat 1: Vera's trade feedback */}
      <div className="panel examiner beat" ref={(el) => { refs.current[0] = el; }}>
        <div className="examiner-head">
          <span className={`vera-react ${(u?.points ?? 0) >= 75 ? "happy" : (u?.points ?? 0) >= 40 ? "hm" : "worried"}`}>
            <PixelSprite name={(u?.points ?? 0) >= 75 ? "vera_pleased" : (u?.points ?? 0) >= 40 ? "vera_neutral" : "vera_concerned"} size={96} title="Vera Atrisk" />
          </span>
          <div className="examiner-text">
            <div className="cro-name">Vera Atrisk · trade feedback</div>
            {r.review && <p className="cro-feedback big">{r.review.reply_text}</p>}
            {r.review?.instruction_attempt && <div className="flag small">⚑ Your answer tried to instruct the grader. That part was ignored; only the finance content was marked.</div>}
            {r.marker === "keywords" && <div className="small muted">Marked by the keyword checker (AI examiner offline).</div>}
          </div>
          <div className="understanding-chip">
            <div className="small muted">Executive Summary</div>
            <div className="u-points"><CountUp value={u ? u.points : 0} format={(v) => v.toFixed(1)} /><span>/100</span></div>
            {u && u.attempts > 1 && <div className="small muted">second try: new checks count half</div>}
            {r.not_sure && <div className="small muted">“I'm not sure”: walkthrough, no points</div>}
          </div>
        </div>
        {!r.not_sure && checks && (
          <ul className="stamps">
            {Object.entries(CHECK_LABELS).map(([k, label], i) => {
              const ok = checks[k as keyof typeof checks];
              return (
                <li key={k} className={`stamp ${ok ? "yes" : "no"}`} style={{ animationDelay: `${0.5 + i * 0.35}s` }}>
                  <span className="stamp-mark">{ok ? "✓" : "✗"}</span>
                  <span>{label}</span>
                  <span className="stamp-pts">{u ? `+${(u.by_check[k] ?? 0).toFixed(1)}` : ""}</span>
                </li>
              );
            })}
          </ul>
        )}
        {r.review && r.review.misconceptions.length > 0 && (
          <div className="misconceptions small"><b>To correct:</b> {r.review.misconceptions.join(" · ")}</div>
        )}
        {beat === 0 && next("See the scoreboard")}
      </div>

      {/* Beat 2: the scoreboard */}
      {beat >= 1 && (
        <div className="panel beat beat-in scoreboard" ref={(el) => { refs.current[1] = el; }}>
          <h2>Q{r.quarter} scoreboard: {r.title ?? props.shock.title}</h2>
          <div className="score-row">
            <div className="score-big">
              <div className="small muted">Results score</div>
              <div className="score-num"><CountUp value={Math.min(100, r.quarter_score)} format={(v) => v.toFixed(0)} ms={1100} /><span>/100</span>{r.quarter_score > 100 && <span className="boom-tag">🏆 beat the pro</span>}</div>
              <div className="stars" aria-label={`${stars} of 3 stars`}>
                {[0, 1, 2].map((i) => <span key={i} className={i < stars ? "star on" : "star"} style={{ animationDelay: `${0.9 + i * 0.28}s` }}>★</span>)}
              </div>
            </div>
            <div className="race-wrap">
              <div className="small muted">Change in surplus this quarter</div>
              <Bars race rows={[
                { label: "You", value: r.comparison.you, boom: r.collapsed?.you },
                { label: "Doing nothing", value: r.comparison.nothing, boom: r.collapsed?.nothing },
                { label: "What a pro would do", value: r.comparison.benchmark, boom: r.collapsed?.benchmark },
              ]} />
            </div>
          </div>
          {r.lever_effects && Object.keys(r.lever_effects).length > 0 && (
            <div className="shields">
              <h3>Your shields: what each position did this quarter</h3>
              <Bars rows={Object.entries(r.lever_effects).map(([k, v]) => ({ label: SHIELD_LABEL[k] ?? k, value: v }))} />
              <div className="small muted">Each bar compares your result with the same quarter without that position.</div>
            </div>
          )}
          {beat === 1 && next("How would a pro have traded?")}
        </div>
      )}

      {/* Beat 3: how a pro would have traded */}
      {beat >= 2 && (
        <div className="panel beat beat-in" ref={(el) => { refs.current[2] = el; }}>
          <h2>How a pro would have traded</h2>
          <p className="small muted"><span className="key-you">●</span> you · <span className="key-pro">●</span> a pro. Highlighted rows are where you and the pro differ. The last column is what matching the pro on that lever alone would have added this quarter; ⭐ marks the one that mattered most.</p>
          <ProTable you={r.your_action} pro={r.benchmark_action} gains={r.lever_gains ?? {}} />
          <WhatIfPanel gameId={r.view.id} quarter={r.quarter} you={r.your_action} />
          {beat === 2 && next("Collect your lesson card")}
        </div>
      )}

      {/* Beat 4: the lesson card */}
      {beat >= 3 && (
        <div className="beat beat-in lesson-wrap" ref={(el) => { refs.current[3] = el; }}>
          <div className="lesson-card">
            <div className="lesson-top"><span>LESSON CARD</span><span>{r.quarter} of {r.n_quarters ?? r.view.n_quarters}</span></div>
            <div className="lesson-icon">{LESSON_ICON[r.quarter] ?? "📘"}</div>
            <div className="lesson-title">{r.title ?? props.shock.title}</div>
            <p className="lesson-text">{r.lesson}</p>
            <div className="lesson-stamp">ADDED TO YOUR COLLECTION</div>
          </div>
        </div>
      )}

      <details className="panel breakdown">
        <summary>Show the full breakdown</summary>
        <div className="two-col">
          <div>
            <h3>Change in surplus, by cause</h3>
            <Bars rows={causes} />
            <div className="small muted">Total {r.total >= 0 ? "+" : "−"}${Math.abs(r.total).toFixed(2)}bn. ✓/✗ shows whether your explanation named the main and second causes. Every number comes from the engine.</div>
          </div>
          <div>
            <h3>Debrief</h3>
            <ul className="debrief">{r.debrief_text.map((t, i) => <li key={i}>{t}</li>)}</ul>
            <p className="small muted">{r.source_note}</p>
          </div>
        </div>
      </details>

      {r.next_is_boss && (
        <div className="boss-warning" role="alert">
          <div className="boss-siren">🚨</div>
          <div><b>INTELLIGENCE BRIEFING · SOMETHING BIG IS COMING</b>
            <div>Every lever is in your hands now. Whatever you hold when the market opens is all you'll have. Spend your last ticket wisely.</div></div>
        </div>
      )}
      <div className="next-bar">
        <button className="gold-btn" onClick={props.onNext}>
          {r.finished ? "See the final debrief →" : r.next_is_boss ? "Prepare for the boss round →" : `On to Q${r.quarter + 1} →`}
        </button>
      </div>
    </section>
  );
}
