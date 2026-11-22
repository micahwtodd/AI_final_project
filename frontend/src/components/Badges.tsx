import { useEffect } from "react";
import type { Achievements, Badge, ReportCard } from "../api";
import { play } from "../sound";
import { PixelSprite } from "./PixelSprite";

/** "Badge unlocked!" cards on the results screen. */
export function BadgeUnlocks(props: { badges: Badge[] }) {
  useEffect(() => {
    if (props.badges.length) {
      const t = setTimeout(() => play("badge"), 900);
      return () => clearTimeout(t);
    }
  }, [props.badges.length]);
  if (!props.badges.length) return null;
  return (
    <div className="unlocks" role="status">
      {props.badges.map((b, i) => (
        <div className="unlock" key={b.id} style={{ animationDelay: `${0.9 + i * 0.25}s` }}>
          <div className="unlock-icon" aria-hidden>{b.icon}</div>
          <div>
            <div className="unlock-kicker">Badge unlocked!</div>
            <b>{b.name}</b>
            <div className="small">{b.text}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Streak counters in the top bar, shown from a run of two. */
export function StreakChips(props: { a: Achievements | undefined }) {
  const s = props.a?.streaks;
  if (!s) return null;
  const n = props.a!.earned.length;
  return (
    <>
      {s.floor >= 2 && <span className="pill streak" title="Quarters in a row above the capital and liquidity floors">🛡️ {s.floor} safe</span>}
      {s.explain >= 2 && <span className="pill streak" title="Quarters in a row you named the main driver">🎯 {s.explain} called</span>}
      {n > 0 && <span className="pill streak" title={props.a!.earned.map((b) => `${b.icon} ${b.name}`).join("\n")}>🏅 {n}/{props.a!.available}</span>}
    </>
  );
}

/** Year-end grade and title. */
export function ReportCardPanel(props: { rc: ReportCard; results: number; understanding: number }) {
  const rc = props.rc;
  const good = rc.grade.startsWith("A") || rc.grade.startsWith("B");
  useEffect(() => {
    const t = setTimeout(() => play(good ? "bell" : "whoosh"), 700);
    return () => clearTimeout(t);
  }, [good]);
  return (
    <div className="panel report-card">
      <div className={`grade-stamp g-${rc.grade[0].toLowerCase()}`}>{rc.grade}</div>
      <div className="rc-body">
        <div className="intro-kicker">Year-end report card</div>
        <h1 className="rc-title">“{rc.title}”</h1>
        <p>{rc.why}</p>
        <div className="small muted">
          Grade = 60% results ({props.results.toFixed(0)}) + 40% understanding ({props.understanding.toFixed(0)}) = {rc.overall.toFixed(1)}.
          {rc.breaches > 0 && ` ${rc.breaches} floor breach${rc.breaches > 1 ? "es" : ""}.`}
        </div>
      </div>
      <PixelSprite name={good ? "vera_pleased" : "vera_concerned"} size={96} title="Vera Atrisk" />
    </div>
  );
}

/** Every badge in the game: earned ones in color, the rest locked. */
export function BadgeShelf(props: { catalog: Omit<Badge, "quarter">[]; earned: Badge[] }) {
  const got = new Map(props.earned.map((b) => [b.id, b]));
  return (
    <div className="panel">
      <h3>Badges · {got.size} of {props.catalog.length}</h3>
      <div className="shelf">
        {props.catalog.map((b) => {
          const e = got.get(b.id);
          return (
            <div key={b.id} className={`shelf-badge ${e ? "got" : "locked"}`} title={b.text}>
              <div className="shelf-icon" aria-hidden>{e ? b.icon : "🔒"}</div>
              <b>{b.name}</b>
              <div className="small muted">{e ? `Q${e.quarter}` : b.text}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
