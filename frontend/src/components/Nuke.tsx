import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { play } from "../sound";

// The collapse, in the game's own pixel world: the crash-office scene, a pixel mushroom cloud rising
// behind the windows, the glass cracking, the cat bolting across the floor, money flying.

const DEBRIS = ["💵", "🏦", "📉", "🏭", "💸", "🧾", "🪙", "🏢", "📊", "💼", "🎩", "🧮"];
const reduced = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// crack lines across the glass, in viewBox units (0..480 x 0..192, the window area of the office art)
const CRACKS = [
  "240,96 210,70 190,40 176,22", "240,96 268,64 300,50 330,24", "240,96 205,112 170,120 130,150",
  "240,96 280,120 320,128 360,160", "240,96 236,140 242,180", "210,70 180,78", "268,64 276,40", "205,112 196,134",
];

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
      <div className="nuke-scene" aria-hidden>
        <div className="nuke-window">
          <img className="nuke-px-cloud" src="/art/nuke_cloud.png" alt="" />
        </div>
        <svg className="nuke-cracks" viewBox="0 0 480 270" preserveAspectRatio="none">
          {CRACKS.map((pts, i) => <polyline key={i} points={pts} style={{ animationDelay: `${0.9 + (i % 4) * 0.08}s` }} />)}
        </svg>
        <img className="nuke-cat" src="/art/cat_alert.png" alt="" />
        <div className="nuke-redwash" />
      </div>
      <div className="nuke-flash" />
      <div className="nuke-stage" aria-hidden>
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
