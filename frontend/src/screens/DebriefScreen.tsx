import { useState } from "react";
import { Nuke } from "../components/Nuke";
import { api, type BeforeAfter, type Debrief, type GameView } from "../api";
import { BadgeShelf, ReportCardPanel } from "../components/Badges";
import { Confetti } from "../components/Fx";
import { LESSON_ICON } from "../labels";

/** Draw the end card on a canvas and download it as a PNG. */
async function downloadCard(company: string, grade: string, title: string, collapsed: boolean, icons: string[],
  calls?: { made: number; correct: number }) {
  try { await document.fonts?.load("700 40px 'Atkinson Hyperlegible'"); } catch { /* the fallback font is fine */ }
  const W = 1000, H = 560, c = document.createElement("canvas");
  c.width = W; c.height = H;
  const g = c.getContext("2d");
  if (!g) return;
  const bg = g.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "#001f5b"); bg.addColorStop(0.6, "#00347a"); bg.addColorStop(1, "#007ac1");
  g.fillStyle = bg; g.fillRect(0, 0, W, H);
  g.strokeStyle = "#ffc72c"; g.lineWidth = 14; g.strokeRect(7, 7, W - 14, H - 14);
  const px = "'Atkinson Hyperlegible', 'Segoe UI', sans-serif";
  g.fillStyle = "#ffc72c"; g.font = `700 30px ${px}`; g.fillText("RISK DESK · EMPLOYEE REVIEW", 50, 70);
  g.fillStyle = "#cfe6f7"; g.font = "24px 'Segoe UI', sans-serif"; g.fillText(company, 50, 108);
  g.fillStyle = "#ffffff"; g.beginPath(); g.arc(160, 280, 95, 0, Math.PI * 2); g.fill();
  g.fillStyle = "#001f5b"; g.font = `700 96px ${px}`; g.textAlign = "center"; g.fillText(grade, 160, 312); g.textAlign = "left";
  g.fillStyle = "#ffffff"; g.font = `700 46px ${px}`; g.fillText(`"${title}"`, 290, 250);
  g.font = "28px 'Segoe UI', sans-serif"; g.fillStyle = "#eaf2fb";
  g.fillText(collapsed ? "💥 Collapsed in the crash" : "🛡️ Survived the Great Depression round", 290, 300);
  if (calls && calls.made) g.fillText(`🎯 Called ${calls.correct} of ${calls.made} quarters`, 290, 345);
  g.font = "56px 'Segoe UI Emoji', 'Apple Color Emoji', sans-serif"; g.fillText(icons.join(" "), 290, 440);
  g.fillStyle = "#cfe6f7"; g.font = "20px 'Segoe UI', sans-serif"; g.fillText("Lesson cards collected", 290, 480);
  const a = document.createElement("a");
  a.href = c.toDataURL("image/png"); a.download = `risk-desk-${company.replace(/\s+/g, "-").toLowerCase()}.png`; a.click();
}

export function DebriefScreen(props: { debrief: Debrief; game: GameView; onRestart: () => void }) {
  const d = props.debrief;
  const pct = (x: number) => `${(100 * (x - d.start_surplus) / d.start_surplus).toFixed(1)}%`;
  const paths = [
    { label: "You", end: d.end_surplus },
    { label: "Doing nothing", end: d.nothing_end_surplus },
    { label: "What a pro would do", end: d.benchmark_end_surplus },
  ];
  const max = Math.max(d.start_surplus, ...paths.map((p) => p.end));
  const [replay, setReplay] = useState(false);
  const [copied, setCopied] = useState(false);
  const bestKey = `riskdesk.best.${props.game.ticker}`;
  const [best] = useState<{ prev: { grade: string; overall: number } | null; isNew: boolean }>(() => {
    try {
      const prev = JSON.parse(localStorage.getItem(bestKey) ?? "null");
      const now = d.report_card ? { grade: d.report_card.grade, overall: d.report_card.overall } : null;
      const isNew = !!now && (!prev || now.overall > prev.overall);
      if (isNew && now) localStorage.setItem(bestKey, JSON.stringify(now));
      return { prev, isNew };
    } catch { return { prev: null, isNew: false }; }
  });
  const rc = d.report_card;
  const shareText = rc ? `Risk Desk · ${props.game.company}: grade ${rc.grade}, "${rc.title}". `
    + `Results ${d.results_score.toFixed(0)}, Executive Summary ${d.understanding_score.toFixed(0)}. `
    + `${d.collapsed ? "Collapsed in the crash." : "Survived the Great Depression round."} `
    + `Lesson cards ${d.lessons.map((l) => LESSON_ICON[l.quarter] ?? "📘").join("")}` : "";

  return (
    <section className="debrief-screen">
      {!d.collapsed && d.report_card && (d.report_card.grade.startsWith("A") || d.report_card.grade.startsWith("B")) && <Confetti pieces={110} />}
      {d.collapsed && <div className="collapse-banner">💥 {props.game.company.toUpperCase()} COLLAPSED · THE ECONOMY IS TOAST 🍞</div>}
      {d.report_card && <ReportCardPanel rc={d.report_card} results={d.results_score} understanding={d.understanding_score} />}
      {replay && <Nuke company={`${props.game.company} (doing nothing)`} surplus={d.nothing_end_surplus} onDone={() => setReplay(false)} />}
      {best.isNew && <div className="best-banner">🏅 New personal best on {props.game.company}{best.prev ? ` (was ${best.prev.grade}, ${best.prev.overall})` : ""}!</div>}
      {!best.isNew && best.prev && <div className="best-banner quiet">Your best on {props.game.company}: {best.prev.grade} ({best.prev.overall}). Try a tougher company?</div>}
      {d.try_next && <div className="try-next"><span className="try-next-tag">TRY THIS NEXT TIME</span> {d.try_next}</div>}
      {!d.collapsed && d.nothing_end_surplus <= 0 && (
        <div className="replay-row no-print">
          <button className="gold-btn" onClick={() => setReplay(true)}>💥 Watch what doing nothing would have done</button>
          <span className="small muted">Same markets, no trades all game: the company collapses in the crash. You kept it alive.</span>
        </div>
      )}
      <div className="two-col">
        <div className="panel center">
          <div className="big-score">{d.results_score.toFixed(0)}<span>/100</span></div>
          <div><b>Results score</b>: how your trades did against doing nothing and what a pro would do</div>
          <div className="small muted">Per quarter: {d.per_quarter.map((x, i) => `Q${i + 1} ${Math.min(100, x).toFixed(0)}`).join(" · ")}
            {d.penalties ? ` · penalties −${d.penalties}` : ""}</div>
        </div>
        <div className="panel center">
          <div className="big-score">{d.understanding_score.toFixed(0)}<span>/100</span></div>
          <div><b>Executive Summary score</b>: how well you explained each quarter to Vera</div>
          <div className="curve" aria-label="Executive Summary score by quarter">
            {Array.from({ length: d.n_quarters ?? 5 }, (_, i) => i + 1).map((q) => {
              const v = d.understanding_per_quarter[String(q)] ?? 0;
              return (
                <div key={q} className="curve-col">
                  <div className="curve-bar" style={{ height: `${Math.max(2, v)}%` }} title={`Q${q}: ${v}`} />
                  <div className="small">Q{q}</div>
                  <div className="small muted">{v.toFixed(0)}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <h3>Surplus at the end</h3>
          <div className="end-bars">
            <div className="end-bar"><div className="fill start" style={{ width: `${(100 * d.start_surplus) / max}%` }} /><span>Start ${d.start_surplus.toFixed(2)}bn</span></div>
            {paths.map((p) => (
              <div className="end-bar" key={p.label}>
                <div className={`fill ${p.label === "You" ? "you" : ""}`} style={{ width: `${(100 * Math.max(0, p.end)) / max}%` }} />
                <span>{p.label} {p.end < 0 ? "−" : ""}${Math.abs(p.end).toFixed(2)}bn ({pct(p.end)}){p.end <= 0 && <span className="boom-tag">💥 COLLAPSED</span>}</span>
              </div>
            ))}
          </div>
          <ul className="debrief">{d.text.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
        <div className="panel">
          <h3>Your lesson cards ({d.lessons.length} of {d.n_quarters ?? 5} collected)</h3>
          <div className="lesson-deck">
            {d.lessons.map((l) => (
              <div key={l.quarter} className="lesson-card mini">
                <div className="lesson-top"><span>Q{l.quarter}</span><span>{LESSON_ICON[l.quarter] ?? "📘"}</span></div>
                <div className="lesson-title">{l.title}</div>
                <p className="lesson-text">{l.lesson}</p>
              </div>
            ))}
          </div>
          <button className="gold-btn wide no-print" onClick={props.onRestart}>Play again</button>
        </div>
      </div>

      {rc && (
        <div className="share-card">
          <div className="share-top"><span>RISK DESK</span><span>{props.game.company}</span></div>
          <div className="share-main">
            <div className={`grade-stamp g-${rc.grade[0].toLowerCase()}`}>{rc.grade}</div>
            <div>
              <div className="share-title">“{rc.title}”</div>
              <div className="share-sub">{d.collapsed ? "💥 Collapsed in the crash" : "🛡️ Survived the Great Depression round"}</div>
              <div className="share-icons">{d.lessons.map((l) => <span key={l.quarter}>{LESSON_ICON[l.quarter] ?? "📘"}</span>)}</div>
              {d.predictions && d.predictions.made > 0 && <div className="share-sub">🎯 Called {d.predictions.correct} of {d.predictions.made} quarters</div>}
            </div>
          </div>
          <div className="share-actions no-print">
            <button className="ghost" onClick={() => downloadCard(props.game.company, rc.grade, rc.title, d.collapsed ?? false,
              d.lessons.map((l) => LESSON_ICON[l.quarter] ?? "📘"), d.predictions)}>⬇ Download card (PNG)</button>
            <button className="ghost" onClick={() => { navigator.clipboard?.writeText(shareText).then(() => setCopied(true)).catch(() => undefined); }}>
              {copied ? "Copied ✓" : "Copy a summary"}
            </button>
          </div>
        </div>
      )}

      <BeforeAfterPanel ba={d.before_after} />

      {d.badge_catalog && <BadgeShelf catalog={d.badge_catalog} earned={d.achievements?.earned ?? []} />}
      <div className="panel no-print">
        <h3>Your feedback</h3>
        <FeedbackBox gameId={props.game.id} />
        <button className="ghost wide" onClick={() => window.print()}>Print session summary</button>
      </div>
      <details className="panel nerd-stats">
        <summary>Nerd stats</summary>
        <div className="small muted">{props.game.company} · seed {props.game.seed} · {d.minutes_played} minutes played · AI usage {props.game.usage?.spend_usd !== undefined ? `$${props.game.usage.spend_usd.toFixed(4)}` : "–"}</div>
      </details>
    </section>
  );
}

const CONCEPT_LABELS: Record<string, string> = {
  duration_gap: "Rate mismatch (duration gap)", surrenders: "Surrenders when rates rise", spread_vs_default: "Spread move vs default",
  forced_selling: "Forced selling and cash", fx_hedge_cost: "Cost of currency hedging", guarantees_equity: "Guarantees and stock markets",
  collateral_counterparty: "Collateral and counterparties", pension_risk_transfer: "Pension risk transfer",
};

function BeforeAfterPanel({ ba }: { ba: BeforeAfter }) {
  if (!ba.quiz_pre) {
    return <div className="panel small muted">The before-the-game quiz was skipped, so there are no before-and-after figures for this session.</div>;
  }
  const mark = (v: boolean | null) => (v === null ? "–" : v ? "✓" : "✗");
  return (
    <div className="panel before-after">
      <h3>What you learned: before and after</h3>
      <p className="small muted">The after-game quiz covers the same five ideas with different questions, so compare idea by idea rather than reading the score change as exact.</p>
      <div className="lab-summary">
        <div className="stat"><b>{ba.quiz_pre.correct}/{ba.quiz_pre.total} → {ba.quiz_post ? `${ba.quiz_post.correct}/${ba.quiz_post.total}` : "–"}</b><span>quiz score{ba.quiz_change_pts !== null ? ` (${ba.quiz_change_pts >= 0 ? "+" : ""}${ba.quiz_change_pts} pts)` : ""}</span></div>
        <div className="stat"><b>{ba.confidence_pre_avg?.toFixed(1)} → {ba.confidence_post_avg?.toFixed(1) ?? "–"}</b><span>average confidence (1 to 5)</span></div>
        <div className="stat"><b>{ba.minutes_played}</b><span>minutes played</span></div>
      </div>
      <div className="two-col" style={{ marginTop: "0.8rem" }}>
        <table className="table small">
          <thead><tr><th>Concept</th><th>Before</th><th>After</th></tr></thead>
          <tbody>{ba.concepts.map((c) => (
            <tr key={c.concept}><td>{CONCEPT_LABELS[c.concept] ?? c.concept}</td><td>{mark(c.pre)}</td><td>{mark(c.post)}</td></tr>
          ))}</tbody>
        </table>
        <table className="table small">
          <thead><tr><th>Confidence</th><th>Before</th><th>After</th></tr></thead>
          <tbody>{ba.confidence_items.map((c) => (
            <tr key={c.id}><td>{c.text}</td><td>{c.pre ?? "–"}</td><td>{c.post ?? "–"}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}

function FeedbackBox({ gameId }: { gameId: string }) {
  const [text, setText] = useState("");
  const [sent, setSent] = useState(false);
  return sent ? <p className="small">Thank you, your feedback was saved.</p> : (
    <div>
      <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)}
        placeholder="What helped you learn? What was confusing? What would you change?" />
      <button className="primary" disabled={!text.trim()} onClick={async () => { await api.feedback(gameId, text); setSent(true); }}>Send feedback</button>
    </div>
  );
}
