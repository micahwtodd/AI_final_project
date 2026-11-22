import { fmtMove } from "../labels";

type Move = { key: string; label: string; value: number | null; unit: string };

// For these, a rise is bad news for an insurer's bond book or a sign of stress, so it is shown red.
const UP_IS_BAD = new Set(["ig_spread_bp", "hy_spread_bp", "ig_loss_pct", "hy_default_pct", "mortgage_loss_pct", "lapse_mult"]);

/** A scrolling ticker of this quarter's market moves (only the engine's own numbers). */
export function MarketTape(props: { moves: Move[]; quarter: number; boss?: boolean }) {
  const items = props.moves.filter((m) => m.value !== 0);
  const cell = (m: Move, k: string) => {
    if (m.value === null) {  // events with no number: frozen markets, a dealer default
      return (
        <span className="tape-item bad" key={k}><span className="tape-label">{m.label.toUpperCase()}</span>
          <span className="tape-val">⚠ {m.unit}</span></span>
      );
    }
    const up = m.key === "lapse_mult" ? m.value > 1 : m.value > 0;
    const bad = UP_IS_BAD.has(m.key) ? up : m.key === "equity_pct" ? !up : null;
    return (
      <span className={`tape-item ${bad === null ? "" : bad ? "bad" : "good"}`} key={k}>
        <span className="tape-label">{m.label.toUpperCase()}</span>
        <span className="tape-val">{up ? "▲" : "▼"} {fmtMove(m.value, m.unit)}</span>
      </span>
    );
  };
  const run = (tag: string) => (
    <div className="tape-run" aria-hidden={tag === "b"}>
      <span className="tape-flash">{props.boss ? "⚠ FINAL QUARTER" : "● BREAKING"} · Q{props.quarter}</span>
      {items.map((m, i) => cell(m, `${tag}${i}`))}
    </div>
  );
  return (
    <div className={`tape ${props.boss ? "boss" : ""}`} role="marquee" aria-label="Market moves this quarter">
      <div className="tape-track" style={{ animationDuration: `${Math.max(14, items.length * 4)}s` }}>
        {run("a")}{run("b")}
      </div>
    </div>
  );
}
