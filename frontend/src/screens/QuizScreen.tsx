import { useEffect, useState } from "react";
import { api, type QuizForm } from "../api";
import { play } from "../sound";

const SCALE = [
  { n: 1, label: "Not at all" }, { n: 2, label: "A little" }, { n: 3, label: "Somewhat" }, { n: 4, label: "Mostly" }, { n: 5, label: "Very" },
];
type Checked = { choice: string; correct: boolean; answer: string; explain: string };

/** One question per card (answer, optionally check it, Next), then all confidence ratings on one page. */
export function QuizScreen(props: {
  gameId: string; when: "pre" | "post"; company: string; demo?: boolean;
  onDone: () => void; onSkip?: () => void; onBack?: () => void;
}) {
  const [form, setForm] = useState<QuizForm | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState<Record<string, Checked>>({});
  const [conf, setConf] = useState<Record<string, number>>({});
  const [step, setStep] = useState(0); // 0..nq-1 questions, nq = confidence page
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.quizForm(props.when).then(setForm).catch((e) => setErr(String(e)));
  }, [props.when]);

  if (!form) return <section className="panel">{err ?? <span className="spinner" />}</section>;
  const pre = props.when === "pre";
  const nq = form.questions.length;
  const q = step < nq ? form.questions[step] : null;
  const c = q ? checked[q.id] : undefined;

  const check = async () => {
    if (!q || !answers[q.id]) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api.checkQuiz(props.gameId, props.when, q.id, answers[q.id]);
      setChecked((x) => ({ ...x, [q.id]: r }));
      setAnswers((a) => ({ ...a, [q.id]: r.choice }));
      play(r.correct ? "bell" : "click");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.submitQuiz(props.gameId, props.when, answers, conf);
      props.onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const optClass = (k: string) => {
    if (!q) return "";
    if (!c) return answers[q.id] === k ? "on" : "";
    if (k === c.answer) return "right";
    if (k === c.choice) return "wrong";
    return "dim";
  };

  return (
    <section className="quiz-flow">
      <div className="quiz-top">
        <div>
          <div className="intro-kicker">{pre ? "Knowledge Check" : "Knowledge Check · after the year"}</div>
          <div className="small muted">
            {pre ? "5 quick questions, then 5 quick ratings. Doesn't count toward your score." : "Same ideas, new questions. See how far you came."}
          </div>
        </div>
        <div className="quiz-top-actions">
          {props.demo && step < nq && (
            <button className="ghost" onClick={() => {
              const letters = ["A", "B", "C", "D"];
              setAnswers(Object.fromEntries(form.questions.map((x, i) => [x.id, checked[x.id]?.choice ?? letters[(i * 3 + (pre ? 1 : 2)) % 4]])));
              setConf(Object.fromEntries(form.confidence.map((x) => [x.id, pre ? 2 : 4])));
              setStep(nq);
            }}>Fill sample answers (demo)</button>
          )}
          {pre && props.onSkip && <button className="link" onClick={props.onSkip}>Skip the quiz</button>}
        </div>
      </div>

      <div className="quiz-progress" aria-label={`Step ${Math.min(step + 1, nq + 1)} of ${nq + 1}`}>
        {Array.from({ length: nq + 1 }, (_, k) => {
          const id = form.questions[k]?.id;
          const mark = id && checked[id] ? (checked[id].correct ? "ok" : "bad") : "";
          return <span key={k} className={`qp ${k < nq ? "q" : "c"} ${k < step ? "done" : k === step ? "now" : ""} ${mark}`} />;
        })}
      </div>

      {q && (
        <div className="quiz-card" key={q.id}>
          <div className="quiz-count">Question {step + 1} of {nq}</div>
          <h2 className="quiz-question">{q.q}</h2>
          <div className="quiz-options" role="radiogroup" aria-label={q.q}>
            {Object.entries(q.options).map(([k, v]) => (
              <button key={k} role="radio" aria-checked={answers[q.id] === k} disabled={!!c}
                className={`quiz-option ${optClass(k)}`}
                onClick={() => setAnswers((a) => ({ ...a, [q.id]: k }))}>
                <span className="opt-letter">{c && k === c.answer ? "✓" : c && k === c.choice ? "✗" : k}</span>{v}
              </button>
            ))}
          </div>
          {c && (
            <div className={`quiz-explain ${c.correct ? "right" : "wrong"}`} role="status">
              <b>{c.correct ? "Correct!" : `Not quite: the answer is ${c.answer}.`}</b> {c.explain}
            </div>
          )}
          {err && <div className="flag small">{err}</div>}
          <div className="quiz-nav">
            <button className="ghost" onClick={() => (step === 0 ? props.onBack?.() : setStep(step - 1))}
              disabled={step === 0 && !props.onBack}>← Back</button>
            <button className="check-btn" disabled={!answers[q.id] || !!c || busy} onClick={check}>
              {c ? "Checked" : "Check answer"}
            </button>
            <button className="primary" disabled={!answers[q.id]} onClick={() => setStep(step + 1)}>Next →</button>
          </div>
        </div>
      )}

      {step >= nq && (
        <div className="quiz-card conf-card">
          <div className="quiz-count">Last step</div>
          <h2 className="quiz-question">How confident are you?</h2>
          <table className="table conf-table">
            <thead>
              <tr><th />{SCALE.map((s) => <th key={s.n} className="conf-head"><b>{s.n}</b><span>{s.label}</span></th>)}</tr>
            </thead>
            <tbody>
              {form.confidence.map((x) => (
                <tr key={x.id}>
                  <td>{x.text}</td>
                  {SCALE.map((s) => (
                    <td key={s.n} className="conf-cell">
                      <button className={`conf-dot ${conf[x.id] === s.n ? "on" : ""}`} aria-label={`${x.text}: ${s.n} (${s.label})`}
                        aria-pressed={conf[x.id] === s.n} onClick={() => setConf((v) => ({ ...v, [x.id]: s.n }))}>{s.n}</button>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {err && <div className="flag small">{err}</div>}
          <div className="quiz-nav">
            <button className="ghost" onClick={() => setStep(nq - 1)}>← Back</button>
            <span className="small muted">{Object.keys(answers).length}/{nq} answered · {Object.keys(conf).length}/{form.confidence.length} rated</span>
            <button className="primary" disabled={busy || Object.keys(answers).length < nq || Object.keys(conf).length < form.confidence.length} onClick={save}>
              {pre ? "Save and go to the desk →" : "Save and see my results →"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
