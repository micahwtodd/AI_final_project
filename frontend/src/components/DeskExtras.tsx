import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { play } from "../sound";

// Small desk moments: the pre-shock prediction, and one light surprise per quarter.

export const PREDICT_OPTIONS: { key: string; label: string; icon: string }[] = [
  { key: "rates_up", label: "Rates jump", icon: "📈" },
  { key: "rates_down", label: "Rates fall", icon: "🔻" },
  { key: "stocks_down", label: "Stocks crash", icon: "📉" },
  { key: "credit", label: "Bonds default", icon: "💳" },
  { key: "everything", label: "Everything at once", icon: "💥" },
];

/** Before the market moves: one tap to call what will hit hardest. For fun; never scored. */
export function PredictModal(props: { quarter: number; onPick: (p: string | null) => void; onCancel: () => void }) {
  useEffect(() => { play("click"); }, []);
  return createPortal(
    <div className="predict-veil" onClick={props.onCancel}>
      <div className="predict-card" role="dialog" aria-label="Make a call" onClick={(e) => e.stopPropagation()}>
        <div className="predict-kicker">BEFORE THE MARKET OPENS · Q{props.quarter}</div>
        <h2>Make the call: what hits hardest this quarter?</h2>
        <p className="small muted">Read the news wire, then pick. It is for bragging rights only; it does not change your score.</p>
        <div className="predict-grid">
          {PREDICT_OPTIONS.map((o) => (
            <button key={o.key} className="predict-opt" onClick={() => props.onPick(o.key)}>
              <span className="predict-icon" aria-hidden>{o.icon}</span>{o.label}
            </button>
          ))}
        </div>
        <div className="predict-foot">
          <button className="ghost" onClick={props.onCancel}>← Back to the desk</button>
          <button className="link" onClick={() => props.onPick(null)}>Skip and end the quarter</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

const SURPRISES: Record<number, string> = {
  1: "☕ Morty spilled coffee on the 10-K. Seamore is drying it page by page with a hair dryer.",
  2: "🎸 Swap Dogg is playing a vinyl record at the trading desk. Nobody has the heart to ask him to stop.",
  3: "🍂 Bonnie brought pumpkin bread. Convexity has already claimed the corner piece.",
  4: "❄️ The office heating broke. Vera is wearing a scarf and has not mentioned it once.",
  5: "📻 The radio crackles: 'markets are jittery this morning.' Everyone pretends not to hear it.",
};
const seen = new Set<string>();

/** One light moment per quarter, shown once, gone after a few seconds. */
export function Surprise(props: { id: string; quarter: number; rule?: string }) {
  const key = `${props.id}-${props.quarter}`;
  const [show, setShow] = useState(!seen.has(key) && !!SURPRISES[props.quarter]);
  useEffect(() => {
    seen.add(key);
    if (!show) return;
    const t = setTimeout(() => setShow(false), 9000);
    return () => clearTimeout(t);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (!show) return null;
  return <div className={`surprise ${props.rule ? "rule" : ""}`} role="status" onClick={() => setShow(false)}>{props.rule ? <>⚡ <b>Rule change:</b> {props.rule}</> : SURPRISES[props.quarter]}</div>;
}
