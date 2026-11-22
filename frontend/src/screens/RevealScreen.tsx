import type { Action, Reveal, Shock } from "../api";
import { LEVERS, type LeverKey } from "../labels";

function Bars(props: { rows: { label: string; value: number }[]; unit?: string }) {
  const max = Math.max(0.01, ...props.rows.map((r) => Math.abs(r.value)));
  return (
    <div className="bars">
      {props.rows.map((r) => (
        <div className="bar-row" key={r.label}>
          <div className="bar-label">{r.label}</div>
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

function describe(a: Partial<Action>): string[] {
  const out = (Object.keys(LEVERS) as LeverKey[]).map((k) => `${LEVERS[k].label}: ${a[k]}${LEVERS[k].unit}`);
  out.push(`Collateral ${a.collateralized ? "on" : "off"}, ${a.dealers} dealer${a.dealers === 3 ? "s" : ""}`);
  if (a.accept_prt !== undefined && a.accept_prt !== null) out.push(`Pension deal: ${a.accept_prt ? "accepted" : "declined"}`);
  return out;
}

export function RevealScreen(props: { reveal: Reveal; shock: Shock; onNext: () => void }) {
  const r = props.reveal;
  const rows = r.attribution.filter((a) => Math.abs(a.value) >= 0.005).sort((a, b) => Math.abs(b.value) - Math.abs(a.value));

  return (
    <section className="reveal">
      <div className="panel">
        <h2>What really happened in Q{r.quarter}: {props.shock.title}</h2>
        <div className="two-col">
          <div>
            <h3>Change in surplus, by cause</h3>
            <Bars rows={rows} />
            <div className="small muted">Total {r.total >= 0 ? "+" : "−"}${Math.abs(r.total).toFixed(2)}bn. Every number comes from the engine.</div>
          </div>
          <div>
            <h3>You vs doing nothing vs the benchmark</h3>
            <Bars rows={[
              { label: "Your trades", value: r.comparison.you },
              { label: "Doing nothing", value: r.comparison.nothing },
              { label: "Benchmark", value: r.comparison.benchmark },
            ]} />
            <div className="score-chip">Quarter score <b>{r.quarter_score.toFixed(0)}</b> / 100</div>
          </div>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <h3>Debrief</h3>
          <ul className="debrief">{r.debrief_text.map((t, i) => <li key={i}>{t}</li>)}</ul>
          <h3>The lesson</h3>
          <p>{r.lesson}</p>
          <p className="small muted">{r.source_note}</p>
        </div>
        <div className="panel">
          <h3>Your ticket vs the benchmark</h3>
          <div className="two-col tight">
            <ul className="small">{describe(r.your_action).map((t) => <li key={t}>{t}</li>)}</ul>
            <ul className="small">{describe(r.benchmark_action).map((t) => <li key={t}>{t}</li>)}</ul>
          </div>
          <button className="primary wide" onClick={props.onNext}>
            {r.finished ? "See the year-end debrief →" : `On to Q${r.quarter + 1} →`}
          </button>
        </div>
      </div>
    </section>
  );
}
