import { useState } from "react";
import { api, type Action, type WhatIf } from "../api";
import { LEVERS, fmtSigned, type LeverKey } from "../labels";
import { play } from "../sound";

/** Rewind the quarter you just played and replay it with a different ticket: same market, nothing changes in your game. */
export function WhatIfPanel(props: { gameId: string; quarter: number; you: Partial<Action> }) {
  const [open, setOpen] = useState(false);
  const [a, setA] = useState<Partial<Action>>({ ...props.you });
  const [res, setRes] = useState<WhatIf | null>(null);
  const [rewinding, setRewinding] = useState(false);
  const keys = Object.keys(LEVERS) as LeverKey[];
  async function replay() {
    setRewinding(true);
    play("whoosh");
    const r = await api.whatif(props.gameId, a).catch(() => null);
    window.setTimeout(() => { setRewinding(false); if (r) { setRes(r); play(r.change > r.actual_change ? "bell" : "click"); } }, 700);
  }
  if (!open) return <button className="ghost whatif-open" onClick={() => setOpen(true)}>⏪ What if? Replay Q{props.quarter} with a different ticket</button>;
  return (
    <div className={`whatif ${rewinding ? "rewinding" : ""}`}>
      <div className="whatif-head"><b>⏪ What if?</b> <span className="muted small">Same market, same seed. Your real game is not changed.</span></div>
      {keys.map((k) => (
        <div className="whatif-row" key={k}>
          <span>{LEVERS[k].label}</span>
          <input type="range" min={LEVERS[k].min} max={LEVERS[k].max} step={LEVERS[k].step} value={Number(a[k] ?? 0)}
            onChange={(e) => setA((x) => ({ ...x, [k]: Number(e.target.value) }))} />
          <b>{Number(a[k] ?? 0).toFixed(0)}{LEVERS[k].unit}</b>
        </div>
      ))}
      <button className="gold-btn" onClick={replay} disabled={rewinding}>{rewinding ? "Rewinding…" : "Replay the quarter"}</button>
      {res && !rewinding && (
        <div className="whatif-res">
          <div className={res.change >= res.actual_change ? "pos" : "neg"}>With this ticket: <b>{fmtSigned(res.change)}</b>{res.collapsed && " 💥 collapsed"}</div>
          <div className="small muted">What you did {fmtSigned(res.actual_change)} · doing nothing {fmtSigned(res.nothing_change)} · a pro {fmtSigned(res.pro_change)}</div>
        </div>
      )}
    </div>
  );
}
