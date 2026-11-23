import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { play } from "../sound";

// A whimsical "the economy just exploded" animation, shown when a company's equity goes to zero or below.
// The cloud is drawn like a real one: a rolling, cauliflower-textured cap with a hot core, a column that
// flares at the bottom, a condensation ring around the stem, and a ground surge spreading outward.

const DEBRIS = ["💵", "🏦", "📉", "🏭", "💸", "🧾", "🪙", "🏢", "📊", "💼", "🎩", "🧮"];
const reduced = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// puffs that give the cap and the ground surge their lumpy edges: [cx, cy, r]
const CAP_PUFFS: [number, number, number][] = [
  [175, 215, 62], [235, 170, 70], [300, 150, 78], [365, 170, 70], [425, 215, 62],
  [205, 265, 58], [260, 245, 66], [340, 245, 66], [395, 265, 58], [300, 215, 80],
];
const ROLL_PUFFS: [number, number, number][] = [
  [150, 285, 40], [205, 305, 44], [265, 315, 46], [335, 315, 46], [395, 305, 44], [450, 285, 40],
];
const SURGE_PUFFS: [number, number, number][] = [
  [60, 655, 42], [130, 640, 52], [210, 630, 58], [300, 625, 62], [390, 630, 58], [470, 640, 52], [540, 655, 42],
];

function Cloud() {
  return (
    <svg className="nuke-cloud" viewBox="0 0 600 700" aria-hidden>
      <defs>
        <filter id="nk-billow" x="-20%" y="-20%" width="140%" height="140%">
          <feTurbulence type="fractalNoise" baseFrequency="0.028" numOctaves="3" seed="7" result="n">
            <animate attributeName="baseFrequency" values="0.026;0.032;0.026" dur="7s" repeatCount="indefinite" />
          </feTurbulence>
          <feDisplacementMap in="SourceGraphic" in2="n" scale="26" xChannelSelector="R" yChannelSelector="G" />
        </filter>
        <filter id="nk-soft"><feGaussianBlur stdDeviation="6" /></filter>
        <radialGradient id="nk-cap" cx="50%" cy="62%" r="60%">
          <stop offset="0%" stopColor="#fff6c8" />
          <stop offset="22%" stopColor="#ffd166" />
          <stop offset="45%" stopColor="#f08a2c" />
          <stop offset="70%" stopColor="#a8452a" />
          <stop offset="100%" stopColor="#4a2a26" />
        </radialGradient>
        <radialGradient id="nk-roll" cx="50%" cy="30%" r="70%">
          <stop offset="0%" stopColor="#c8642e" />
          <stop offset="60%" stopColor="#6e3326" />
          <stop offset="100%" stopColor="#2e1c1c" />
        </radialGradient>
        <linearGradient id="nk-stem" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="#4a2a26" />
          <stop offset="30%" stopColor="#b8582c" />
          <stop offset="50%" stopColor="#ffc35a" />
          <stop offset="70%" stopColor="#b8582c" />
          <stop offset="100%" stopColor="#4a2a26" />
        </linearGradient>
        <linearGradient id="nk-surge" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#9a6a52" />
          <stop offset="100%" stopColor="#3c2a26" />
        </linearGradient>
      </defs>

      {/* ground surge: a low skirt of dust rolling outward */}
      <g className="nk-surge" filter="url(#nk-billow)">
        <ellipse cx="300" cy="668" rx="290" ry="40" fill="url(#nk-surge)" />
        {SURGE_PUFFS.map(([x, y, r], i) => <circle key={i} cx={x} cy={y} r={r} fill="url(#nk-surge)" />)}
      </g>

      {/* the column: narrow under the cap, flaring into the dust at the bottom, hottest in the middle */}
      <g className="nk-stem" filter="url(#nk-billow)">
        <path d="M268 300 C262 400 258 500 236 590 C222 630 190 650 160 668 L440 668 C410 650 378 630 364 590 C342 500 338 400 332 300 Z"
          fill="url(#nk-stem)" />
      </g>

      {/* condensation ring around the stem */}
      <g className="nk-collar" filter="url(#nk-billow)">
        <ellipse cx="300" cy="455" rx="125" ry="22" fill="none" stroke="#efe2d2" strokeOpacity="0.55" strokeWidth="18" filter="url(#nk-soft)" />
        <ellipse cx="300" cy="455" rx="118" ry="19" fill="none" stroke="#fff6ea" strokeOpacity="0.3" strokeWidth="5" />
      </g>

      {/* the cap: a rolling torus underneath, a cauliflower dome on top, a glowing core inside */}
      <g className="nk-cap">
        <g filter="url(#nk-billow)">
          {ROLL_PUFFS.map(([x, y, r], i) => <circle key={i} cx={x} cy={y} r={r} fill="url(#nk-roll)" />)}
          <ellipse cx="300" cy="235" rx="200" ry="105" fill="url(#nk-cap)" />
          {CAP_PUFFS.map(([x, y, r], i) => <circle key={i} cx={x} cy={y} r={r} fill="url(#nk-cap)" />)}
        </g>
        <ellipse className="nk-core" cx="300" cy="250" rx="95" ry="45" fill="#fff4c0" filter="url(#nk-soft)" />
      </g>
    </svg>
  );
}

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
        <Cloud />
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
