import { useEffect, useRef, useState, type CSSProperties } from "react";
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
  const [pos, setPos] = useState<CSSProperties>({});
  const ref = useRef<HTMLDivElement>(null);
  const btn = useRef<HTMLButtonElement>(null);
  // Keep the menu inside the window wherever the button sits (the top bar wraps on narrow screens).
  const place = () => {
    const r = btn.current?.getBoundingClientRect();
    if (!r) return;
    const w = Math.min(340, window.innerWidth - 32);
    const left = Math.max(16, Math.min(r.right - w, window.innerWidth - w - 16));
    setPos({ position: "fixed", top: r.bottom + 6, left, width: w, right: "auto", maxHeight: window.innerHeight - r.bottom - 22, overflowY: "auto" });
  };
  useEffect(() => {
    if (!open) return;
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => { window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true); };
  }, [open]);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const go = (fn: () => void) => () => { setOpen(false); fn(); };
  const g = props.game;

  return (
    <div className="hood" ref={ref}>
      <button ref={btn} className="pill hood-btn" aria-expanded={open} onClick={() => setOpen(!open)}>Under the hood ▾</button>
      {open && (
        <div className="hood-menu" role="menu" style={pos}>
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
            <b>AI cap</b> {props.capUsd !== null ? `$${props.capUsd.toFixed(2)} per game, fixed` : "$0.25 per game, fixed"}: click the token meter to see spend by agent.
          </div>
          {!g && <div className="hood-row small muted">Start a game to see its trace and switch modes.</div>}
        </div>
      )}
    </div>
  );
}
