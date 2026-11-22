import { useState } from "react";
import { api, type BeforeAfter, type Debrief, type GameView } from "../api";
import { BadgeShelf, ReportCardPanel } from "../components/Badges";
import { Confetti } from "../components/Fx";

export function DebriefScreen(props: { debrief: Debrief; game: GameView; onRestart: () => void }) {
  const d = props.debrief;
  const pct = (x: number) => `${(100 * (x - d.start_surplus) / d.start_surplus).toFixed(1)}%`;
  const paths = [
    { label: "You", end: d.end_surplus },
    { label: "Doing nothing", end: d.nothing_end_surplus },
    { label: "Benchmark", end: d.benchmark_end_surplus },
  ];
  const max = Math.max(d.start_surplus, ...paths.map((p) => p.end));

  return (
    <section className="debrief-screen">
      {d.report_card && (d.report_card.grade.startsWith("A") || d.report_card.grade.startsWith("B")) && <Confetti pieces={110} />}
      {d.report_card && <ReportCardPanel rc={d.report_card} results={d.results_score} understanding={d.understanding_score} />}
      <div className="muted center-text">Year-end debrief · {props.game.company} · seed {props.game.seed} · {d.minutes_played} minutes played</div>
      <div className="two-col">
        <div className="panel center">
          <div className="big-score">{d.results_score.toFixed(0)}<span>/100</span></div>
          <div><b>Results score</b>: how your trades did against doing nothing and the benchmark</div>
          <div className="small muted">Per quarter: {d.per_quarter.map((x, i) => `Q${i + 1} ${x.toFixed(0)}`).join(" · ")}
            {d.penalties ? ` · penalties −${d.penalties}` : ""}</div>
        </div>
        <div className="panel center">
          <div className="big-score">{d.understanding_score.toFixed(0)}<span>/100</span></div>
          <div><b>Executive Summary score</b>: how well you explained each quarter to Vera</div>
          <div className="curve" aria-label="Executive Summary score by quarter">
            {[1, 2, 3, 4].map((q) => {
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
          <h3>Surplus at year end</h3>
          <div className="end-bars">
            <div className="end-bar"><div className="fill start" style={{ width: `${(100 * d.start_surplus) / max}%` }} /><span>Start ${d.start_surplus.toFixed(2)}bn</span></div>
            {paths.map((p) => (
              <div className="end-bar" key={p.label}>
                <div className={`fill ${p.label === "You" ? "you" : ""}`} style={{ width: `${(100 * Math.max(0, p.end)) / max}%` }} />
                <span>{p.label} ${p.end.toFixed(2)}bn ({pct(p.end)})</span>
              </div>
            ))}
          </div>
          <ul className="debrief">{d.text.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
        <div className="panel">
          <h3>The four lessons</h3>
          {d.lessons.map((l) => (
            <div key={l.quarter} className="lesson">
              <b>Q{l.quarter} · {l.title}</b>
              <p className="small">{l.lesson}</p>
            </div>
          ))}
          <button className="primary wide no-print" onClick={props.onRestart}>Play again</button>
        </div>
      </div>

      <BeforeAfterPanel ba={d.before_after} />

      {d.badge_catalog && <BadgeShelf catalog={d.badge_catalog} earned={d.achievements?.earned ?? []} />}
      <div className="panel no-print">
        <h3>Your feedback</h3>
        <FeedbackBox gameId={props.game.id} />
        <button className="ghost wide" onClick={() => window.print()}>Print session summary</button>
      </div>
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
      <div className="lab-summary">
        <div className="stat"><b>{ba.quiz_pre.correct}/8 → {ba.quiz_post ? `${ba.quiz_post.correct}/8` : "–"}</b><span>quiz score{ba.quiz_change_pts !== null ? ` (${ba.quiz_change_pts >= 0 ? "+" : ""}${ba.quiz_change_pts} pts)` : ""}</span></div>
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
