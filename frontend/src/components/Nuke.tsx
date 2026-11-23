import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { play } from "../sound";

// A whimsical "the economy just exploded" animation, shown when a company's equity goes to zero or below.
// Cartoon only: a flash, a mushroom cloud of smoke puffs, a shockwave, and money and buildings flying off.

const DEBRIS = ["💵", "🏦", "📉", "🏭", "💸", "🧾", "🪙", "🏢", "📊", "💼", "🎩", "🧮"];
// The mushroom cap: a ring of puffs, then two rows building the dome on top (x, y offsets in px, size).
const CAP: [number, number, number][] = [
  ...Array.from({ length: 10 }, (_, i): [number, number, number] => {
    const a = (i / 10) * 2 * Math.PI;
    return [Math.cos(a) * 140, Math.sin(a) * 42, 120];
  }),
  [-90, -60, 130], [-30, -78, 140], [40, -78, 140], [100, -58, 125],
  [-45, -125, 120], [30, -130, 125], [0, -10, 150],
];
const reduced = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export function Nuke(props: { company: string; surplus: number; onDone?: () => void }) {
  const [open, setOpen] = useState(true);
  useEffect(() => {
    play("boom");
    document.body.classList.add("quake");
    const t = setTimeout(() => document.body.classList.remove("quake"), 1400);
    return () => { clearTimeout(t); document.body.classList.remove("quake"); };
  }, []);
  if (!open) return null;
  const close = () => { setOpen(false); props.onDone?.(); };
  const still = reduced();
  return createPortal(
    <div className={`nuke ${still ? "still" : ""}`} role="alertdialog" aria-label="Your company collapsed" onClick={close}>
      <div className="nuke-flash" />
      <div className="nuke-sky" />
      <div className="nuke-stage" aria-hidden>
        <div className="nuke-ring" />
        <div className="nuke-ring r2" />
        <div className="nuke-stem">
          {Array.from({ length: 7 }, (_, i) => <span key={i} style={{ ["--i" as string]: i }} />)}
        </div>
        <div className="nuke-cap">
          {CAP.map(([x, y, d], i) => <span key={i} style={{ left: x - d / 2, top: y - d / 2, width: d, height: d, animationDelay: `${-i * 0.17}s` }} />)}
        </div>
        <div className="nuke-collar">
          {Array.from({ length: 6 }, (_, i) => <span key={i} style={{ ["--i" as string]: i }} />)}
        </div>
        <div className="nuke-sign">ECONOMY</div>
        {DEBRIS.map((d, i) => {
          const ang = (i / DEBRIS.length) * 2 * Math.PI + 0.3;
          const dist = 280 + ((i * 53) % 160);
          return (
            <span key={i} className="nuke-debris" style={{
              ["--dx" as string]: `${Math.cos(ang) * dist}px`, ["--dy" as string]: `${Math.sin(ang) * dist * 0.7 - 160}px`,
              ["--spin" as string]: `${((i * 97) % 900) - 450}deg`, animationDelay: `${0.35 + (i % 4) * 0.06}s`,
            }}>{d}</span>
          );
        })}
      </div>
      <div className="nuke-text">
        <div className="nuke-kaboom">KA-BOOM!</div>
        <div className="nuke-title">{props.company} has collapsed</div>
        <div className="nuke-sub">Equity hit <b>{props.surplus < 0 ? "−" : ""}${Math.abs(props.surplus).toFixed(2)}bn</b>. The economy is toast. 🍞</div>
        <button className="gold-btn" onClick={close}>Survey the wreckage →</button>
        <div className="nuke-fine">(No real economies were harmed in the making of this simulation.)</div>
      </div>
    </div>,
    document.body,
  );
}
