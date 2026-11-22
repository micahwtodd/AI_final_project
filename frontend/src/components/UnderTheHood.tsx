import { useEffect, useRef, useState } from "react";
import type { AgentMode, GameView } from "../api";

/** One place for everything a grader needs: trace, experiments, safety lab, mode switch, budget cap. */
export function UnderTheHood(props: {
  game: GameView | null;
  onTrace: () => void;
  onSafety: () => void;
  onExperiments: () => void;
  onMode: (m: AgentMode) => void;
  capUsd: number | null;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const go = (fn: () => void) => () => { setOpen(false); fn(); };
  const g = props.game;

  return (
    <div className="hood" ref={ref}>
      <button className="pill hood-btn" aria-expanded={open} onClick={() => setOpen(!open)}>Under the hood ▾</button>
      {open && (
        <div className="hood-menu" role="menu">
          <button role="menuitem" disabled={!g} onClick={go(props.onTrace)}>
            <b>Trace</b><span>Every delegation, tool call, model call and cost in this session</span>
          </button>
          <button role="menuitem" onClick={go(props.onExperiments)}>
            <b>Experiments</b><span>Solo vs Team, routing, retrieval size, caching: measured tokens and cost</span>
          </button>
          <button role="menuitem" onClick={go(props.onSafety)}>
            <b>Safety Lab</b><span>Attacks with defenses off vs on, teaching accuracy, examiner reliability</span>
          </button>
          <div className="hood-row">
            <b>Colleagues</b>
            <div className="seg">
              <button className={g?.agent_mode === "team" ? "on" : ""} disabled={!g} onClick={go(() => props.onMode("team"))}>Team</button>
              <button className={g?.agent_mode === "solo" ? "on" : ""} disabled={!g} onClick={go(() => props.onMode("solo"))}>Solo</button>
            </div>
          </div>
          <div className="hood-row small muted">
            <b>Budget cap</b> {props.capUsd !== null ? `$${props.capUsd}` : "set once a game starts"}: click the token meter to change it.
          </div>
          {!g && <div className="hood-row small muted">Start a game to see its trace and switch modes.</div>}
        </div>
      )}
    </div>
  );
}
