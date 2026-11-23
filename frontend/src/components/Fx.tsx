import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { play } from "../sound";
import { SEASONS, SEASON_ICON, SEASON_NAME } from "../labels";

// Overlays go straight onto <body>: the screen transition animates a transform, which would
// otherwise pin position:fixed overlays to the page instead of the window.

const reduced = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Text that types itself out, like a teletype. */
export function Typewriter(props: { text: string; cps?: number }) {
  const [n, setN] = useState(reduced() ? props.text.length : 0);
  useEffect(() => {
    if (reduced() || document.hidden) { setN(props.text.length); return; }
    setN(0);
    let i = 0;
    const t = window.setInterval(() => { i += 2; setN(Math.min(props.text.length, i)); if (i >= props.text.length) clearInterval(t); },
      Math.round(2000 / (props.cps ?? 70)));
    return () => clearInterval(t);
  }, [props.text]); // eslint-disable-line react-hooks/exhaustive-deps
  return <>{props.text.slice(0, n)}{n < props.text.length && <span className="caret">▍</span>}</>;
}

/** A number that counts up (or down) to its value. */
export function CountUp(props: { value: number; format: (v: number) => string; ms?: number; from?: number }) {
  const [shown, setShown] = useState(props.from ?? 0);
  const last = useRef(props.from ?? 0);
  useEffect(() => {
    // reduced motion, or a hidden tab (where animation frames pause): show the final number at once
    if (reduced() || document.hidden) { setShown(props.value); last.current = props.value; return; }
    const start = last.current, end = props.value, dur = props.ms ?? 900, t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      setShown(start + (end - start) * e);
      if (k < 1) raf = requestAnimationFrame(tick);
      else last.current = end;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [props.value, props.ms]);
  return <>{props.format(shown)}</>;
}

const COLORS = ["#007AC1", "#001F5B", "#FFC72C", "#6CACE4", "#2E8540", "#C8102E"];

/** A one-off burst of confetti from the top of the screen. */
export function Confetti(props: { pieces?: number }) {
  const [on, setOn] = useState(!reduced());
  const n = props.pieces ?? 70;
  const ended = useRef(0);
  useEffect(() => {
    const t = setTimeout(() => setOn(false), 8000); // safety net; normally removed when the last piece lands
    return () => clearTimeout(t);
  }, []);
  if (!on) return null;
  return createPortal(
    <div className="confetti" aria-hidden onAnimationEnd={() => { ended.current += 1; if (ended.current >= n) setOn(false); }}>
      {Array.from({ length: n }, (_, i) => {
        const left = (i * 37) % 100;
        const style = {
          left: `${left}%`, background: COLORS[i % COLORS.length],
          animationDelay: `${((i * 53) % 60) / 100}s`, animationDuration: `${1.8 + ((i * 29) % 12) / 10}s`,
          ["--drift" as string]: `${((i * 71) % 160) - 80}px`, ["--spin" as string]: `${((i * 97) % 720) - 360}deg`,
        };
        return <span key={i} style={style} className={i % 3 === 0 ? "round" : ""} />;
      })}
    </div>,
    document.body,
  );
}

/** Full-width banner that sweeps in at the start of a quarter. Click to dismiss. */
const seen = new Set<string>();
export function QuarterSplash(props: { id: string; quarter: number; of: number; boss?: boolean; title: string; era?: string }) {
  const key = `${props.id}-${props.quarter}`;
  const [show, setShow] = useState(!seen.has(key));
  const boss = !!props.boss;
  useEffect(() => {
    seen.add(key);
    if (!show) return;
    play(boss ? "alarm" : "whoosh");
    const t = setTimeout(() => setShow(false), reduced() ? 900 : boss ? 7000 : 5000); // fallback; normally ends with the sweep
    return () => clearTimeout(t);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (!show) return null;
  return createPortal(
    <div className={`q-splash ${boss ? "boss" : ""}`} onClick={() => setShow(false)} role="status">
      <div className="q-splash-band" onAnimationEnd={(e) => { if (e.animationName === "band-in" || e.animationName === "boss-in") setShow(false); }}>
        {boss ? (
          <>
            <div className="q-splash-boss">⚠ FINAL QUARTER · THE CRASH ⚠</div>
            <div className="q-splash-q">BOSS ROUND</div>
            <div className="q-splash-title">{props.title}. Survive this one.</div>
          </>
        ) : (
          <>
            <div className="q-splash-q">QUARTER {props.quarter} <span>of {props.of} · {SEASON_ICON[SEASONS[props.quarter]]} {SEASON_NAME[SEASONS[props.quarter]]}</span></div>
            <div className="q-splash-title">{props.title}</div>
          </>
        )}
        {props.era && <div className="q-splash-era">{props.era}</div>}
      </div>
    </div>,
    document.body,
  );
}
