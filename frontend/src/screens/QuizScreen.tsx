import { useEffect, useState } from "react";
import { api, type QuizForm } from "../api";

const SCALE = [1, 2, 3, 4, 5];

export function QuizScreen(props: { gameId: string; when: "pre" | "post"; company: string; demo?: boolean; onDone: () => void; onSkip?: () => void }) {
  const [form, setForm] = useState<QuizForm | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [conf, setConf] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.quizForm(props.when).then(setForm).catch((e) => setErr(String(e)));
  }, [props.when]);

  if (!form) return <section className="panel">{err ?? <span className="spinner" />}</section>;
  const complete = form.questions.every((q) => answers[q.id]) && form.confidence.every((c) => conf[c.id]);
  const pre = props.when === "pre";

  return (
    <section className="quiz">
      <div className="panel">
        <h1>{pre ? "Before you start" : "After the year"}: 8 quick questions</h1>
        <p className="muted">
          {pre
            ? `This takes about three minutes and does not affect your game score. At the end you will answer a second set on the same ideas, so you can see what you learned running ${props.company}.`
            : "Same ideas as before, different questions. Then rate your confidence again, so you can see how far you came."}
        </p>
      </div>

      <div className="panel">
        <h3>Questions</h3>
        <ol className="quiz-list">
          {form.questions.map((q) => (
            <li key={q.id}>
              <div className="quiz-q">{q.q}</div>
              <div className="quiz-opts" role="radiogroup" aria-label={q.q}>
                {Object.entries(q.options).map(([k, v]) => (
                  <label key={k} className={`quiz-opt ${answers[q.id] === k ? "on" : ""}`}>
                    <input type="radio" name={q.id} value={k} checked={answers[q.id] === k}
                      onChange={() => setAnswers((a) => ({ ...a, [q.id]: k }))} />
                    <b>{k}</b> {v}
                  </label>
                ))}
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="panel">
        <h3>How confident are you? (1 = not at all, 5 = very)</h3>
        <table className="table conf-table">
          <tbody>
            {form.confidence.map((c) => (
              <tr key={c.id}>
                <td>{c.text}</td>
                <td className="conf-scale" role="radiogroup" aria-label={c.text}>
                  {SCALE.map((n) => (
                    <label key={n} className={`conf-dot ${conf[c.id] === n ? "on" : ""}`}>
                      <input type="radio" name={c.id} value={n} checked={conf[c.id] === n} onChange={() => setConf((x) => ({ ...x, [c.id]: n }))} />
                      {n}
                    </label>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {err && <div className="flag small">{err}</div>}
        <div className="start-row">
          {pre && props.onSkip && <button className="ghost" onClick={props.onSkip}>Skip the quiz</button>}
          {props.demo && (
            <button className="ghost" onClick={() => {
              const letters = ["A", "B", "C", "D"];
              setAnswers(Object.fromEntries(form.questions.map((q, i) => [q.id, letters[(i * 3 + (pre ? 1 : 2)) % 4]])));
              setConf(Object.fromEntries(form.confidence.map((c) => [c.id, pre ? 2 : 4])));
            }}>Fill sample answers (demo)</button>
          )}
          <span className="small muted">{Object.keys(answers).length}/{form.questions.length} answered · {Object.keys(conf).length}/{form.confidence.length} rated</span>
          <button className="primary" disabled={!complete || busy} onClick={async () => {
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
          }}>{pre ? "Save and go to the desk →" : "Save and see my results →"}</button>
        </div>
      </div>
    </section>
  );
}
