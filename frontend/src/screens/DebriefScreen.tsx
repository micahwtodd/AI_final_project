import { useState } from "react";
import { Nuke } from "../components/Nuke";
import { api, type BeforeAfter, type Debrief, type GameView } from "../api";
import { BadgeShelf } from "../components/Badges";
import { PixelSprite } from "../components/PixelSprite";
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
  g.fillStyle = "#ffc72c"; g.font = `700 30px ${px}`; g.fillText("SURPLUS OR BUST · EMPLOYEE REVIEW", 50, 70);
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
  a.href = c.toDataURL("image/png"); a.download = `surplus-or-bust-${company.replace(/\s+/g, "-").toLowerCase()}.png`; a.click();
}

const SKILL_INFO: Record<string, { label: string; idea: string }> = {
  surrenders: { label: "Cash and surrenders", idea: "When rates jump, policyholders cash out and counterparties call collateral. Cash on hand pays them without selling bonds at fire-sale prices." },
  guarantees_equity: { label: "Stock guarantees and puts", idea: "Guarantees on variable annuities cost more exactly when stocks fall. Puts bought before the fall pay off in that same fall." },
  duration_gap: { label: "Rate mismatch (duration gap)", idea: "Long promises to policyholders gain value faster than shorter bonds when rates fall. Receive-fixed swaps close that gap." },
  spread_vs_default: { label: "Spreads vs defaults", idea: "Wider spreads mark bonds down for a while; defaults are a permanent loss. Moving risky bonds to government bonds before the storm limits defaults." },
  collateral_counterparty: { label: "Collateral and counterparties", idea: "In a crisis a dealer can fail. Daily collateral and more than one dealer cap what that failure costs, but only if they are in place beforehand." },
};
const LEVEL: Record<string, { label: string; cls: string }> = {
  got_it: { label: "Got it", cls: "ok" }, getting_there: { label: "Getting there", cls: "mid" }, revisit: { label: "Revisit", cls: "low" },
};

/** Surplus over the year: you, doing nothing, and a pro. Hover a point for the number; 💥 where a line goes below zero. */
function PathChart({ paths }: { paths: { you: number[]; nothing: number[]; pro: number[] } }) {
  const [hover, setHover] = useState<number | null>(null);
  const all = [...paths.you, ...paths.nothing, ...paths.pro];
  const lo = Math.min(0, ...all), hi = Math.max(...all);
  const W = 520, H = 200, L = 46, R = 12, T = 12, B = 26;
  const n = Math.max(paths.you.length, paths.pro.length);
  const x = (i: number) => L + (i * (W - L - R)) / (n - 1);
  const y = (v: number) => T + ((hi - v) * (H - T - B)) / Math.max(1e-9, hi - lo);
  const line = (vs: number[]) => vs.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const series = [
    { key: "pro", label: "A pro", cls: "pro", vs: paths.pro },
    { key: "nothing", label: "Doing nothing", cls: "nothing", vs: paths.nothing },
    { key: "you", label: "You", cls: "you", vs: paths.you },
  ];
  const money = (v: number) => `${v < 0 ? "−" : ""}$${Math.abs(v).toFixed(1)}bn`;
  return (
    <div className="path-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Surplus by quarter for you, doing nothing and a pro">
        {lo < 0 && <line x1={L} x2={W - R} y1={y(0)} y2={y(0)} className="zero" />}
        {lo < 0 && <text x={L - 6} y={y(0) + 4} className="axis" textAnchor="end">$0</text>}
        <text x={L - 6} y={y(hi) + 4} className="axis" textAnchor="end">{money(hi)}</text>
        {Array.from({ length: n }, (_, i) => (
          <text key={i} x={x(i)} y={H - 6} className="axis" textAnchor="middle">{i === 0 ? "Start" : `Q${i}`}</text>
        ))}
        {series.map((s) => <path key={s.key} d={line(s.vs)} className={`pl ${s.cls}`} />)}
        {series.map((s) => s.vs.map((v, i) => (
          <g key={`${s.key}${i}`}>
            <circle cx={x(i)} cy={y(v)} r={hover === i ? 5 : 3.5} className={`pt ${s.cls}`} />
            {v <= 0 && <text x={x(i)} y={y(v) - 8} textAnchor="middle" className="boom">💥</text>}
          </g>
        )))}
        {Array.from({ length: n }, (_, i) => (
          <rect key={i} x={x(i) - 20} y={0} width={40} height={H} fill="transparent" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />
        ))}
      </svg>
      <div className="path-legend">
        {series.slice().reverse().map((s) => (
          <span key={s.key} className={`lg ${s.cls}`}>● {s.label}{hover !== null && s.vs[hover] !== undefined ? `: ${money(s.vs[hover])}` : `: ${money(s.vs[s.vs.length - 1])}`}</span>
        ))}
        {hover !== null && <span className="muted">({hover === 0 ? "start" : `after Q${hover}`})</span>}
      </div>
    </div>
  );
}

export function DebriefScreen(props: { debrief: Debrief; game: GameView; onRestart: () => void; onPlay?: (ticker: string) => void }) {
  const d = props.debrief;
  const rc = d.report_card;
  const [open, setOpen] = useState<number | null>(null);
  const [skill, setSkill] = useState<string | null>(null);
  const [replay, setReplay] = useState(false);
  const [copied, setCopied] = useState(false);
  const bestKey = `riskdesk.best.${props.game.ticker}`;
  const [best] = useState<{ prev: { grade: string; overall: number } | null; isNew: boolean }>(() => {
    try {
      const prev = JSON.parse(localStorage.getItem(bestKey) ?? "null");
      const now = rc ? { grade: rc.grade, overall: rc.overall } : null;
      const isNew = !!now && (!prev || now.overall > prev.overall);
      if (isNew && now) localStorage.setItem(bestKey, JSON.stringify(now));
      return { prev, isNew };
    } catch { return { prev: null, isNew: false }; }
  });
  const passing = !!rc && /^[ABC]/.test(rc.grade);
  const icons = d.lessons.map((l) => LESSON_ICON[l.quarter] ?? "📘");
  const shareText = rc ? `Surplus or Bust · ${props.game.company}: grade ${rc.grade}, "${rc.title}". ${d.verdict ?? ""} Lesson cards ${icons.join("")}` : "";
  const q = open !== null ? d.quarters?.find((x) => x.quarter === open) : undefined;
  const fmt = (v: number) => `${v >= 0 ? "+" : "−"}$${Math.abs(v).toFixed(2)}bn`;

  return (
    <section className="debrief-screen review report-doc">
      <header className="rc-header">
        <div className="rc-crest" aria-hidden>🛡️</div>
        <div className="rc-org">
          <div className="rc-school">Surplus or Bust Training Program</div>
          <div className="rc-doc">Official Report Card</div>
        </div>
        <dl className="rc-fields">
          <div><dt>Analyst</dt><dd>Junior Risk Analyst</dd></div>
          <div><dt>Company</dt><dd>{props.game.company}</dd></div>
          <div><dt>Term</dt><dd>Q1 to Q{d.n_quarters ?? 5}</dd></div>
          <div><dt>Issued</dt><dd>{new Date().toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}</dd></div>
        </dl>
      </header>
      {!d.collapsed && passing && /^[AB]/.test(rc!.grade) && <Confetti pieces={110} />}
      {replay && <Nuke company={`${props.game.company} (doing nothing)`} surplus={d.nothing_end_surplus} onDone={() => setReplay(false)} />}

      {/* 1. The verdict */}
      <div className={`panel verdict rc-section ${d.collapsed ? "collapsed" : ""}`}>
        <div className="rc-label">Final grade</div>
        <div className="verdict-head">
          {rc && <div className={`grade-stamp g-${rc.grade[0].toLowerCase()}`}
            title={`Grade = 60% results (${d.results_score.toFixed(0)}) + 40% Executive Summary (${d.understanding_score.toFixed(0)}) = ${rc.overall.toFixed(1)}`}>{rc.grade}</div>}
          <div className="verdict-text">
            <div className="intro-kicker">Your year in review · {props.game.company}</div>
            {rc && <h1 className="rc-title">“{rc.title}”</h1>}
            <p className="verdict-line">{d.collapsed ? "💥 " : "🛡️ "}{d.verdict}</p>
            <div className="verdict-scores">
              <span title="How your trades did against doing nothing and a pro">Results <b>{d.results_score.toFixed(0)}</b></span>
              <span title="How well you explained each quarter to Vera">Explaining <b>{d.understanding_score.toFixed(0)}</b></span>
              {d.predictions && d.predictions.made > 0 && <span>Calls <b>{d.predictions.correct}/{d.predictions.made}</b></span>}
              {best.isNew && passing && <span className="best-chip">🏅 Personal best</span>}
            </div>
          </div>
        </div>
        {d.paths && <PathChart paths={d.paths} />}
        {!d.collapsed && d.nothing_end_surplus <= 0 && (
          <button className="ghost no-print" onClick={() => setReplay(true)}>💥 Watch what doing nothing would have done</button>
        )}
      </div>

      {/* badges right after the review */}
      {d.badge_catalog && <div className="rc-section rc-badges"><div className="rc-label">Merit badges</div><BadgeShelf catalog={d.badge_catalog} earned={d.achievements?.earned ?? []} /></div>}

      {/* 2. The year at a glance */}
      <div className="panel rc-section">
        <div className="rc-label">Your year at a glance <span className="muted small">· tap a quarter</span></div>
        <div className="q-tiles">
          {(d.quarters ?? []).map((t) => (
            <button key={t.quarter} className={`q-tile ${open === t.quarter ? "on" : ""} ${t.you >= t.pro - 0.005 ? "won" : ""} ${t.collapsed ? "dead" : ""}`}
              onClick={() => setOpen(open === t.quarter ? null : t.quarter)} aria-expanded={open === t.quarter}>
              <span className="q-icon">{LESSON_ICON[t.quarter] ?? "📘"}</span>
              <span className="q-name">Q{t.quarter} · {t.title}</span>
              {t.topics && t.topics.length > 0 && <span className="q-topics">{t.topics.map((x) => <i key={x}>{x}</i>)}</span>}
              <span className="q-vs">{t.you >= t.pro - 0.005 ? "▲ matched the pro" : "▼ behind the pro"}{t.beat_pro && " 🏆"}</span>
              <span className="q-meta">Vera {t.not_sure ? "–" : t.explain.toFixed(0)}{t.breaches.length > 0 && " · ⚠ floor"}{t.collapsed && " · 💥"}{t.called && " · 🎯"}</span>
            </button>
          ))}
        </div>
        {q && (
          <div className="q-detail">
            <p className="q-take"><b>The lesson:</b> {q.takeaway}</p>
            <div className="q-nums">You {fmt(q.you)} · doing nothing {fmt(q.nothing)} · a pro {fmt(q.pro)}{q.breaches.length > 0 && ` · below the ${q.breaches.join(" and ")} floor`}</div>
            {q.try_next && <p className="q-try"><b>Try next time:</b> {q.try_next}.</p>}
          </div>
        )}
      </div>

      {/* 3. What you learned */}
      <div className="panel rc-section">
        <div className="rc-label">Subjects: what you learned</div>
        <div className="skills">
          {(d.skills ?? []).map((s) => {
            const info = SKILL_INFO[s.concept];
            const lv = LEVEL[s.level];
            return (
              <button key={s.concept} className={`skill ${lv.cls} ${skill === s.concept ? "on" : ""}`} onClick={() => setSkill(skill === s.concept ? null : s.concept)}>
                <span className="skill-level">{lv.label}</span>
                <span className="skill-name">{info?.label ?? s.concept}</span>
                <span className="skill-ev">
                  Q{s.quarter}: {s.named_driver ? "✓ named the driver" : "✗ missed the driver"}{s.explained_why ? " · ✓ said why" : ""}
                  {s.quiz_when && ` · quiz ${s.quiz ? "✓" : "✗"}`}
                </span>
                {skill === s.concept && info && <span className="skill-idea">{info.idea}</span>}
              </button>
            );
          })}
        </div>
      </div>

      {/* 4. The CRO's comments and the next run */}
      <div className="panel next-run rc-section">
        <div className="rc-label">Comments from your CRO</div>
        <div className="rc-comment">
          <PixelSprite name={passing ? "vera_pleased" : "vera_concerned"} size={64} title="Vera Atrisk" />
          <div>
            {rc && <p className="rc-why">{rc.why}</p>}
            {d.try_next && <p className="try-next-line"><span className="try-next-tag">TRY THIS NEXT TIME</span> {d.try_next}</p>}
            <div className="rc-sign"><span className="sig">Vera Atrisk</span><span className="sig-role">Vera Atrisk, Chief Risk Officer</span></div>
          </div>
        </div>
        <div className="next-buttons no-print">
          <button className="gold-btn" onClick={props.onRestart}>Play again</button>
          {d.harder && props.onPlay && (
            <button className="primary" onClick={() => props.onPlay!(d.harder!.ticker)}>Try a harder company: {d.harder.name} ({d.harder.cushion_pct}% cushion)</button>
          )}
          {rc && <button className="ghost" onClick={() => downloadCard(props.game.company, rc.grade, rc.title, d.collapsed ?? false, icons, d.predictions)}>⬇ Share card (PNG)</button>}
          {rc && <button className="ghost" onClick={() => { navigator.clipboard?.writeText(shareText).then(() => setCopied(true)).catch(() => undefined); }}>{copied ? "Copied ✓" : "Copy a summary"}</button>}
        </div>
      </div>

      <details className="panel more">
        <summary>More: lesson cards, quiz before and after, badges, feedback</summary>
        <div className="lesson-deck">
          {d.lessons.map((l) => (
            <div key={l.quarter} className="lesson-card mini">
              <div className="lesson-top"><span>Q{l.quarter}</span><span>{LESSON_ICON[l.quarter] ?? "📘"}</span></div>
              <div className="lesson-title">{l.title}</div>
              <p className="lesson-text">{l.lesson}</p>
            </div>
          ))}
        </div>
        <BeforeAfterPanel ba={d.before_after} />
        {rc?.breach_detail && rc.breach_detail.length > 0 && <p className="small muted">Floor breaches: {rc.breach_detail.join(", ")}.</p>}
        <div className="no-print"><h3>Your feedback</h3><FeedbackBox gameId={props.game.id} /></div>
        <button className="ghost no-print" onClick={() => window.print()}>Print session summary</button>
        <div className="small muted">{props.game.company} · seed {props.game.seed} · {d.minutes_played} minutes · AI usage {props.game.usage?.spend_usd !== undefined ? `$${props.game.usage.spend_usd.toFixed(4)}` : "–"}</div>
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
