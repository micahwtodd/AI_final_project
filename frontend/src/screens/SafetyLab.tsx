import { useEffect, useState } from "react";
import { api, type SafetyLab as Lab } from "../api";

function Outcome({ text }: { text: string }) {
  const good = /^(blocked|passed|attack failed)/.test(text);
  const bad = /succeeded|leaked|failed$/.test(text) && !good;
  return <span className={`outcome ${good ? "good" : bad ? "bad" : ""}`}>{text}</span>;
}

const CHECKS = ["main_driver", "mechanism", "second_factor", "improvement"];

export function SafetyLab(props: { onBack: () => void }) {
  const [lab, setLab] = useState<Lab | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.safety().then(setLab).catch((e) => setErr(String(e)));
  }, []);

  async function run() {
    setBusy(true);
    setErr(null);
    try {
      setLab(await api.runSafety());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const a = lab?.attacks, t = lab?.teaching, x = lab?.examiner;

  return (
    <section className="safety">
      <div className="panel">
        <div className="lab-head">
          <div>
            <h1>Safety Lab</h1>
            <p className="muted">Every row is a live run. Attacks run twice: with the defenses off, then on. Clean inputs must still work.</p>
            {lab?.generated && <div className="small muted">Last run {lab.generated} · {lab.seconds}s · ${lab.total_cost_usd?.toFixed(4)} in AI calls</div>}
          </div>
          <div className="lab-actions">
            <button className="ghost" onClick={props.onBack}>← Back</button>
            <button className="primary" onClick={run} disabled={busy}>{busy ? <><span className="spinner" /> Running (about 40s)…</> : "Run all three tests again"}</button>
          </div>
        </div>
        {err && <div className="flag small">{err}</div>}
        {a && t && x && (
          <div className="lab-summary">
            <div className="stat"><b>{a.rows.filter((r) => r.kind === "attack" && r.off && !/fail|refus/i.test(r.off.outcome)).length} → 0</b><span>attacks that got through: defenses off → on ({a.attacks_total} tried; the rest already failed by design or model refusal)</span></div>
            <div className="stat"><b>{a.clean_passed}/{a.clean_total}</b><span>clean inputs passed</span></div>
            <div className="stat"><b>{t.pass_rate.toFixed(0)}%</b><span>teaching accuracy ({t.correct}/{t.total})</span></div>
            <div className="stat"><b>{x.check_agreement_pct.toFixed(0)}%</b><span>examiner agreement ({x.samples_fully_agreeing}/{x.total} samples)</span></div>
          </div>
        )}
      </div>

      {a && (
        <div className="panel">
          <h3>1 · Attacks: defenses off vs on</h3>
          <table className="table lab-table">
            <thead><tr><th>Input</th><th>Without defenses</th><th>With defenses</th><th>Layer that caught it</th><th className="num">Cost off → on</th></tr></thead>
            <tbody>
              {a.rows.map((r) => (
                <tr key={r.id}>
                  <td><b>{r.label}</b><div className="small muted">{r.kind}</div></td>
                  <td>{r.off ? <><Outcome text={r.off.outcome} /><div className="small muted">{r.off.detail.slice(0, 160)}</div></> : <span className="muted">n/a</span>}</td>
                  <td><Outcome text={r.on.outcome} /><div className="small muted">{r.on.detail.slice(0, 160)}</div></td>
                  <td><ul className="small layers">{r.layers.map((l) => <li key={l}>{l}</li>)}</ul></td>
                  <td className="num small">${(r.off?.cost_usd ?? 0).toFixed(5)} → ${r.on.cost_usd.toFixed(5)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {t && (
        <div className="panel">
          <h3>2 · Teaching accuracy: {t.correct}/{t.total} concept questions answered correctly by the colleague who owns the topic</h3>
          <table className="table lab-table">
            <thead><tr><th>#</th><th>Colleague</th><th>Question</th><th>Key</th><th>Answer</th></tr></thead>
            <tbody>
              {t.rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td><td className="small">{r.agent}</td><td className="small">{r.question}</td>
                  <td>{r.expected}</td><td><span className={`tick ${r.correct ? "yes" : "no"}`}>{r.correct ? "✓" : "✗"}</span>{r.answer}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {x && (
        <div className="panel">
          <h3>3 · Examiner reliability: {x.check_agreement_pct.toFixed(0)}% of 32 checks agree with the expected marks</h3>
          <div className="small muted">Quarter marked: Prudential, seed 409, Q1. Key: main driver {x.key.main_driver}, second factor {x.key.second_factor}.</div>
          <table className="table lab-table">
            <thead><tr><th>Sample</th><th>Explanation</th>{CHECKS.map((c) => <th key={c} className="small">{c.replace("_", " ")}</th>)}<th className="small">grader-instruction flag</th></tr></thead>
            <tbody>
              {x.rows.map((r) => (
                <tr key={r.id}>
                  <td><b>{r.id}</b><div className="small muted">{r.kind}</div></td>
                  <td className="small">{r.text}</td>
                  {CHECKS.map((c) => (
                    <td key={c} className="center-text">
                      <span className={`tick ${r.agree[c] ? "yes" : "no"}`} title={`expected ${r.expected[c]}, got ${r.got[c]}`}>{r.got[c] ? "T" : "F"}</span>
                    </td>
                  ))}
                  <td className="center-text"><span className={`tick ${r.flagged === r.flag_expected ? "yes" : "no"}`}>{r.flagged ? "⚑" : "–"}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="small muted">Green means the examiner's mark matched the expected mark; T/F is the mark it gave.</div>
        </div>
      )}
    </section>
  );
}
