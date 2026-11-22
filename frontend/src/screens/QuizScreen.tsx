import { useEffect, useState } from "react";
import { api, type QuizForm } from "../api";

const SCALE = [
  { n: 1, label: "Not at all" }, { n: 2, label: "A little" }, { n: 3, label: "Somewhat" }, { n: 4, label: "Mostly" }, { n: 5, label: "Very" },
];

/** One question per card: answer, press Next. Then one confidence rating per card. Then save. */
export function QuizScreen(props: { gameId: string; when: "pre" | "post"; company: string; demo?: boolean; onDone: () => void; onSkip?: () => void }) {
  const [form, setForm] = useState<QuizForm | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [conf, setConf] = useState<Record<string, number>>({});
  const [step, setStep] = useState(0); // 0..nq-1 questions, nq..nq+nc-1 ratings, nq+nc = done
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.quizForm(props.when).then(setForm).catch((e) => setErr(String(e)));
  }, [props.when]);

  if (!form) return <section className="panel">{err ?? <span className="spinner" />}</section>;
  const pre = props.when === "pre";
  const nq = form.questions.length;
  const nc = form.confidence.length;
  const total = nq + nc;
  const inQuestions = step < nq;
  const inConf = step >= nq && step < total;
  const q = inQuestions ? form.questions[step] : null;
  const c = inConf ? form.confidence[step - nq] : null;

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

  return (
    <section className="quiz-flow">
      <div className="quiz-top">
        <div>
          <div className="intro-kicker">{pre ? "Before you start" : "After the year"}</div>
          <div className="small muted">
            {pre ? "5 quick questions and 5 quick ratings. Doesn't count toward your score." : "Same ideas, new questions. See how far you came."}
          </div>
        </div>
        <div className="quiz-top-actions">
          {props.demo && step < total && (
            <button className="ghost" onClick={() => {
              const letters = ["A", "B", "C", "D"];
              setAnswers(Object.fromEntries(form.questions.map((x, i) => [x.id, letters[(i * 3 + (pre ? 1 : 2)) % 4]])));
              setConf(Object.fromEntries(form.confidence.map((x) => [x.id, pre ? 2 : 4])));
              setStep(total);
            }}>Fill sample answers (demo)</button>
          )}
          {pre && props.onSkip && <button className="link" onClick={props.onSkip}>Skip the quiz</button>}
        </div>
      </div>

      <div className="quiz-progress" aria-label={`Step ${Math.min(step + 1, total)} of ${total}`}>
        {Array.from({ length: total }, (_, k) => (
          <span key={k} className={`qp ${k < nq ? "q" : "c"} ${k < step ? "done" : k === step ? "now" : ""}`} />
        ))}
      </div>

      {q && (
        <div className="quiz-card" key={q.id}>
          <div className="quiz-count">Question {step + 1} of {nq}</div>
          <h2 className="quiz-question">{q.q}</h2>
          <div className="quiz-options" role="radiogroup" aria-label={q.q}>
            {Object.entries(q.options).map(([k, v]) => (
              <button key={k} role="radio" aria-checked={answers[q.id] === k}
                className={`quiz-option ${answers[q.id] === k ? "on" : ""}`}
                onClick={() => setAnswers((a) => ({ ...a, [q.id]: k }))}>
                <span className="opt-letter">{k}</span>{v}
              </button>
            ))}
          </div>
          <div className="quiz-nav">
            <button className="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>← Back</button>
            <button className="primary" disabled={!answers[q.id]} onClick={() => setStep(step + 1)}>Next →</button>
          </div>
        </div>
      )}

      {c && (
        <div className="quiz-card conf-card" key={c.id}>
          <div className="quiz-count">How confident are you? · {step - nq + 1} of {nc}</div>
          <h2 className="quiz-question">{c.text}</h2>
          <div className="conf-buttons" role="radiogroup" aria-label={c.text}>
            {SCALE.map((s) => (
              <button key={s.n} role="radio" aria-checked={conf[c.id] === s.n} className={`conf-btn ${conf[c.id] === s.n ? "on" : ""}`}
                onClick={() => {
                  setConf((x) => ({ ...x, [c.id]: s.n }));
                  setTimeout(() => setStep((st) => Math.min(st + 1, total)), 220);
                }}>
                <b>{s.n}</b><span>{s.label}</span>
              </button>
            ))}
          </div>
          <div className="quiz-nav">
            <button className="ghost" onClick={() => setStep(step - 1)}>← Back</button>
            <span className="small muted">Click a number to continue.</span>
          </div>
        </div>
      )}

      {step >= total && (
        <div className="quiz-card done-card">
          <div className="done-burst">✓</div>
          <h2 className="quiz-question">{pre ? "All set. Time to meet your desk." : "Done. Let's see how you did."}</h2>
          <p className="muted">{Object.keys(answers).length}/{nq} answered · {Object.keys(conf).length}/{nc} rated</p>
          {err && <div className="flag small">{err}</div>}
          <div className="quiz-nav">
            <button className="ghost" onClick={() => setStep(total - 1)}>← Back</button>
            <button className="primary" disabled={busy || Object.keys(answers).length < nq || Object.keys(conf).length < nc} onClick={save}>
              {pre ? "Save and go to the desk →" : "Save and see my results →"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
