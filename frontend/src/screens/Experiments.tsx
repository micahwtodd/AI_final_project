import { useEffect, useState } from "react";

// The Experiments page: E1 to E4 and the cost projections, read from evidence/experiments.json
// (written by scripts/experiments.py). Every token count is what the provider reported.

type Sum = { questions: number; errors: number; facts_found: number; facts_total: number; two_views_on_decisions: number; decision_questions: number;
  avg_cost_usd: number; total_cost_usd: number; avg_seconds: number; avg_tokens: Record<string, number>; cached_share: number };
type Row = { id: string; question: string; reply: string; specialist_answers: { agent_name: string; text: string }[]; facts_found: number; facts_total: number;
  cost_usd: number; seconds: number; two_views: boolean; specialists: string[]; facts: { name: string; found: boolean; target?: number }[] };
type Data = {
  generated?: string; model?: string;
  E1?: { solo: Row[]; team: Row[]; solo_summary: Sum; team_summary: Sum };
  E2?: { all_summary: Sum; route_summary: Sum | null; all: Row[] };
  E3?: { runs: { ticker: string; variant: string; seconds: number; searches: number; chunks_read: number; tokens: Record<string, number>; cost_usd: number;
    accepted: Record<string, number>; rejected: number }[]; fields_changed: Record<string, Record<string, { targeted: number | null; large: number | null }>>; note?: string };
  E4?: { on_summary: Sum; off_summary: Sum; note?: string };
  examiner?: { tokens: Record<string, number>; cost_usd: number };
  projections?: { assumptions: Record<string, string | number>; tokens_per_session: Record<string, number>;
    models: Record<string, { per_session: number; per_learner_month: number; learners_100_month: number; learners_10000_month: number }>;
    calibration_one_time_per_company_usd: number; cap: Record<string, number> };
};

const usd = (v: number, d = 4) => `$${v.toFixed(d)}`;
const pct = (a: number, b: number) => (b ? `${Math.round((100 * a) / b)}%` : "–");

function SumRow({ label, s }: { label: string; s?: Sum | null }) {
  if (!s) return null;
  return (
    <tr>
      <td><b>{label}</b></td>
      <td>{s.facts_found}/{s.facts_total} ({pct(s.facts_found, s.facts_total)})</td>
      <td>{s.two_views_on_decisions}/{s.decision_questions}</td>
      <td>{(s.avg_tokens.input ?? 0).toLocaleString()} in · {(s.avg_tokens.cached ?? 0).toLocaleString()} cached · {(s.avg_tokens.output ?? 0).toLocaleString()} out</td>
      <td>{usd(s.avg_cost_usd)}</td>
      <td>{s.avg_seconds}s</td>
    </tr>
  );
}

function SumTable({ rows }: { rows: [string, Sum | null | undefined][] }) {
  return (
    <table className="table exp-table">
      <thead><tr><th></th><th>Engine facts in the answer</th><th>Two views on decision questions</th><th>Tokens per question (avg)</th><th>Cost per question</th><th>Time</th></tr></thead>
      <tbody>{rows.map(([l, s]) => <SumRow key={l} label={l} s={s} />)}</tbody>
    </table>
  );
}

export function Experiments(props: { onBack: () => void }) {
  const [d, setD] = useState<Data | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { fetch("/api/experiments").then((r) => r.json()).then(setD).catch(() => setD({})); }, []);
  if (!d) return <section className="panel">Loading…</section>;
  if (!d.generated) return (
    <section className="panel"><h1>Experiments</h1><p className="muted">No results yet. Run <code>python scripts/experiments.py</code>.</p>
      <button className="ghost" onClick={props.onBack}>← Back</button></section>
  );
  const pairs = d.E1 ? d.E1.solo.map((s) => ({ s, t: d.E1!.team.find((x) => x.id === s.id) })) : [];
  return (
    <section className="experiments">
      <div className="panel">
        <button className="ghost" onClick={props.onBack}>← Back</button>
        <h1>Experiments</h1>
        <p className="muted">Measured {d.generated} on {d.model}. Every token count is what the provider reported; costs use the course price table.
          Ten fixed questions, Jackson Financial, seed 409, start of Q1. Facts are marked by code against the engine.</p>
      </div>

      {d.E1 && (
        <div className="panel">
          <h2>E1 · Solo versus Team</h2>
          <SumTable rows={[["Solo (Vera alone, every tool)", d.E1.solo_summary], ["Team (Vera routes to specialists)", d.E1.team_summary]]} />
          <h3>The ten answer pairs (for Micah to read and judge)</h3>
          {pairs.map(({ s, t }) => (
            <div key={s.id} className="exp-pair">
              <button className="link" onClick={() => setOpen(open === s.id ? null : s.id)}>
                {open === s.id ? "▾" : "▸"} {s.id}: {s.question} <span className="muted">· Solo {s.facts_found}/{s.facts_total}, Team {t?.facts_found}/{t?.facts_total}</span>
              </button>
              {open === s.id && (
                <div className="two-col">
                  <div className="exp-ans"><b>Solo</b> <span className="muted small">{usd(s.cost_usd)} · {s.seconds}s</span><p>{s.reply}</p></div>
                  <div className="exp-ans"><b>Team</b> <span className="muted small">{t && `${usd(t.cost_usd)} · ${t.seconds}s · asked ${t.specialists.join(", ") || "nobody"}`}</span>
                    {t?.specialist_answers.map((x, i) => <p key={i} className="small"><b>{x.agent_name}:</b> {x.text}</p>)}
                    <p><b>Vera:</b> {t?.reply}</p></div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {d.E2 && (
        <div className="panel">
          <h2>E2 · Routing versus asking every specialist</h2>
          <SumTable rows={[["Team, Vera routes (from E1)", d.E2.route_summary], ["Team, ask all three", d.E2.all_summary]]} />
        </div>
      )}

      {d.E3 && (
        <div className="panel">
          <h2>E3 · Reading the 10-K: targeted (k=4) versus a large read</h2>
          <table className="table exp-table">
            <thead><tr><th>Company</th><th>Variant</th><th>Fields found</th><th>Searches · chunks read</th><th>Tokens (in · cached · out)</th><th>Cost</th><th>Time</th></tr></thead>
            <tbody>{d.E3.runs.map((r, i) => (
              <tr key={i}><td>{r.ticker}</td><td>{r.variant}</td><td>{Object.keys(r.accepted).length} ({r.rejected} rejected)</td>
                <td>{r.searches} · {r.chunks_read}</td><td>{r.tokens.input.toLocaleString()} · {r.tokens.cached.toLocaleString()} · {r.tokens.output.toLocaleString()}</td>
                <td>{usd(r.cost_usd)}</td><td>{r.seconds}s</td></tr>
            ))}</tbody>
          </table>
          <h3>Profile fields that changed between the two reads</h3>
          {d.E3.note && <p className="small muted">{d.E3.note}</p>}
          {Object.entries(d.E3.fields_changed).map(([t, diff]) => (
            <p key={t} className="small"><b>{t}:</b> {Object.keys(diff).length === 0 ? "no change" :
              Object.entries(diff).map(([k, v]) => `${k} ${v.targeted ?? "–"} → ${v.large ?? "–"}`).join("; ")}</p>
          ))}
        </div>
      )}

      {d.E4 && (
        <div className="panel">
          <h2>E4 · Prompt caching on versus off (Solo, ten questions)</h2>
          <table className="table exp-table">
            <thead><tr><th></th><th>Cached share of input</th><th>Tokens per question (avg)</th><th>Cost per question</th><th>Time</th></tr></thead>
            <tbody>{([["Caching on (stable prefix)", d.E4.on_summary], ["Caching off (prefix broken)", d.E4.off_summary]] as [string, Sum][]).map(([l, s]) => (
              <tr key={l}><td><b>{l}</b></td><td>{Math.round(100 * s.cached_share)}%</td>
                <td>{(s.avg_tokens.input ?? 0).toLocaleString()} in · {(s.avg_tokens.cached ?? 0).toLocaleString()} cached</td><td>{usd(s.avg_cost_usd)}</td><td>{s.avg_seconds}s</td></tr>
            ))}</tbody>
          </table>
          {d.E4.note && <p className="small muted">{d.E4.note}</p>}
        </div>
      )}

      {d.projections && (
        <div className="panel">
          <h2>What it would cost to run</h2>
          <p className="small muted">{String(d.projections.assumptions.note)} Assumes {d.projections.assumptions.team_questions_per_session} team questions and {d.projections.assumptions.examiner_calls_per_session} explanations
            per session, {d.projections.assumptions.sessions_per_learner_month} sessions per learner per month.</p>
          <table className="table exp-table">
            <thead><tr><th>Model</th><th>Per session</th><th>Per learner per month</th><th>100 learners per month</th><th>10,000 learners per month</th></tr></thead>
            <tbody>{Object.entries(d.projections.models).map(([m, v]) => (
              <tr key={m}><td><b>{m}</b>{m === d.model && " (used)"}</td><td>{usd(v.per_session)}</td><td>{usd(v.per_learner_month, 3)}</td>
                <td>${v.learners_100_month.toLocaleString()}</td><td>${v.learners_10000_month.toLocaleString()}</td></tr>
            ))}</tbody>
          </table>
          <p className="small">One-time calibration per company (Seamore reading the 10-K): <b>{usd(d.projections.calibration_one_time_per_company_usd)}</b>.
            The per-session cap of ${d.projections.cap.per_session_usd} bounds spend at ${d.projections.cap.max_per_learner_month} per learner per month
            (${d.projections.cap.max_10000_month.toLocaleString()} for 10,000 learners), whatever the model does.</p>
        </div>
      )}
    </section>
  );
}
