import type { Debrief, GameView } from "../api";

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
      <div className="panel center">
        <div className="muted">Year-end debrief · {props.game.company} · seed {props.game.seed}</div>
        <div className="big-score">{d.results_score.toFixed(0)}<span>/100</span></div>
        <div>Results score</div>
        <div className="small muted">Per quarter: {d.per_quarter.map((x, i) => `Q${i + 1} ${x.toFixed(0)}`).join(" · ")}
          {d.penalties ? ` · penalties −${d.penalties}` : ""} · {d.minutes_played} minutes played</div>
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
          <button className="primary wide" onClick={props.onRestart}>Play again</button>
        </div>
      </div>
    </section>
  );
}
