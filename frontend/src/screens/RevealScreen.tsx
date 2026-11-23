import type { Action, Reveal, Shock } from "../api";
import { LEVERS, type LeverKey } from "../labels";
import { PixelSprite } from "../components/PixelSprite";
import { Confetti, CountUp } from "../components/Fx";
import { BadgeUnlocks } from "../components/Badges";

type Row = { key?: string; label: string; value: number; mark?: "yes" | "no" };

function Bars(props: { rows: Row[]; unit?: string }) {
  const max = Math.max(0.01, ...props.rows.map((r) => Math.abs(r.value)));
  return (
    <div className="bars">
      {props.rows.map((r) => (
        <div className="bar-row" key={r.label}>
          <div className="bar-label">
            {r.mark && <span className={`tick ${r.mark}`} title={r.mark === "yes" ? "You named this" : "You did not name this"}>{r.mark === "yes" ? "✓" : "✗"}</span>}
            {r.label}
          </div>
          <div className="bar-track">
            <div className="bar-mid" />
            <div className={`bar ${r.value < 0 ? "neg" : "pos"}`}
              style={{ width: `${(50 * Math.abs(r.value)) / max}%`, [r.value < 0 ? "right" : "left"]: "50%" }} />
          </div>
          <div className={`bar-value ${r.value < 0 ? "neg" : "pos"}`}>{r.value >= 0 ? "+" : "−"}{Math.abs(r.value).toFixed(2)}{props.unit ?? "bn"}</div>
        </div>
      ))}
    </div>
  );
}

/** One row per lever, with your setting and the pro's side by side; rows where you differ are highlighted. */
function TicketTable(props: { you: Partial<Action>; pro: Partial<Action> }) {
  const { you, pro } = props;
  const rows: [string, string, string][] = (Object.keys(LEVERS) as LeverKey[]).map((k) => [
    LEVERS[k].label, `${you[k] ?? 0}${LEVERS[k].unit}`, `${pro[k] ?? 0}${LEVERS[k].unit}`]);
  rows.push(["Collateral", you.collateralized ? "On" : "Off", pro.collateralized ? "On" : "Off"]);
  rows.push(["Dealers", String(you.dealers ?? 1), String(pro.dealers ?? 1)]);
  if (pro.accept_prt !== undefined && pro.accept_prt !== null)
    rows.push(["Pension deal", you.accept_prt ? "Accepted" : "Declined", pro.accept_prt ? "Accepted" : "Declined"]);
  return (
    <table className="table ticket-table">
      <thead><tr><th></th><th>You</th><th>What a pro would do</th></tr></thead>
      <tbody>
        {rows.map(([label, y, p]) => (
          <tr key={label} className={y !== p ? "differs" : ""}><td>{label}</td><td>{y}</td><td>{p}</td></tr>
        ))}
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

export function RevealScreen(props: { reveal: Reveal; shock: Shock; onNext: () => void }) {
  const r = props.reveal;
  const checks = r.review?.checks;
  const markFor = (key: string): Row["mark"] => {
    if (!checks || r.not_sure) return undefined;
    if (key === r.main_driver) return checks.main_driver ? "yes" : "no";
    if (key === r.second_factor) return checks.second_factor ? "yes" : "no";
    return undefined;
  };
  const rows: Row[] = r.attribution
    .filter((a) => Math.abs(a.value) >= 0.005)
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .map((a) => ({ key: a.key, label: a.label, value: a.value, mark: markFor(a.key) }));
  const u = r.understanding;

  return (
    <section className="reveal">
      {((u?.points ?? 0) >= 75 || r.quarter_score >= 75) && <Confetti />}
      <BadgeUnlocks badges={r.badges_new ?? []} />
      <div className="panel examiner">
        <div className="examiner-head">
          <PixelSprite name={(u?.points ?? 0) >= 50 ? "vera_pleased" : "vera_concerned"} size={72} title="Vera Atrisk" />
          <div className="examiner-text">
            <div className="cro-name">Vera Atrisk · trade feedback</div>
            {r.review && <p className="cro-feedback">{r.review.reply_text}</p>}
            {r.review?.instruction_attempt && <div className="flag small">⚑ Your answer tried to instruct the grader. That part was ignored; only the finance content was marked.</div>}
            {r.marker === "keywords" && <div className="small muted">Marked by the keyword checker (AI examiner offline).</div>}
          </div>
          <div className="understanding-chip">
            <div className="small muted">Executive Summary this quarter</div>
            <div className="u-points"><CountUp value={u ? u.points : 0} format={(v) => v.toFixed(1)} /><span>/100</span></div>
            {u && u.attempts > 1 && <div className="small muted">second try: new checks count half</div>}
            {r.not_sure && <div className="small muted">“I'm not sure”: walkthrough, no points</div>}
          </div>
        </div>
        {!r.not_sure && checks && (
          <ul className="checks">
            {Object.entries(CHECK_LABELS).map(([k, label]) => (
              <li key={k} className={checks[k as keyof typeof checks] ? "yes" : "no"}>
                <span className={`tick ${checks[k as keyof typeof checks] ? "yes" : "no"}`}>{checks[k as keyof typeof checks] ? "✓" : "✗"}</span>
                {label} <span className="muted small">{u ? `+${(u.by_check[k] ?? 0).toFixed(1)}` : ""}</span>
              </li>
            ))}
          </ul>
        )}
        {r.review && r.review.misconceptions.length > 0 && (
          <div className="misconceptions small"><b>To correct:</b> {r.review.misconceptions.join(" · ")}</div>
        )}
      </div>

      <div className="panel">
        <h2>What really happened in Q{r.quarter}: {props.shock.title}</h2>
        <div className="two-col">
          <div>
            <h3>Change in surplus, by cause</h3>
            <Bars rows={rows} />
            <div className="small muted">Total {r.total >= 0 ? "+" : "−"}${Math.abs(r.total).toFixed(2)}bn. ✓/✗ shows whether your explanation named the main and second causes. Every number comes from the engine.</div>
          </div>
          <div>
            <h3>You vs doing nothing vs what a pro would do</h3>
            <Bars rows={[
              { label: "Your trades", value: r.comparison.you },
              { label: "Doing nothing", value: r.comparison.nothing },
              { label: "What a pro would do", value: r.comparison.benchmark },
            ]} />
            <div className="score-chip">Results score this quarter <b><CountUp value={r.quarter_score} format={(v) => v.toFixed(0)} ms={1100} /></b> / 100</div>
            <h3 style={{ marginTop: "1rem" }}>What would have helped most</h3>
            <ul className="small">{r.improvement_facts.map((t) => <li key={t}>{t}</li>)}</ul>
          </div>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <h3>The lesson</h3>
          <p>{r.lesson}</p>
          <h3>Debrief</h3>
          <ul className="debrief">{r.debrief_text.map((t, i) => <li key={i}>{t}</li>)}</ul>
          <p className="small muted">{r.source_note}</p>
        </div>
        <div className="panel">
          <h3>Your ticket vs what a pro would do</h3>
          <TicketTable you={r.your_action} pro={r.benchmark_action} />
          <button className="primary wide" onClick={props.onNext}>
            {r.finished ? "See the year-end debrief →" : `On to Q${r.quarter + 1} →`}
          </button>
        </div>
      </div>
    </section>
  );
}
