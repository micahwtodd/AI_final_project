import { useEffect, useMemo, useRef, useState } from "react";
import { api, type Action, type GameView, type Preview, type Shock, type Usage } from "../api";
import { ChatPanel } from "../components/ChatPanel";
import { COUNTERPARTY_TIP, LEVERS, TICKET_TIP, UNLOCK_INTRO, UNLOCK_Q, type LeverKey } from "../labels";
import { PixelSprite } from "../components/PixelSprite";

const LEVER_KEYS = Object.keys(LEVERS) as LeverKey[];
type Deltas = Record<LeverKey, number>;
type Terms = Pick<Action, "collateralized" | "dealers" | "accept_prt">;
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const fmtNum = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1));
import { Meters } from "../components/Meters";
import { BalanceSheetPanel } from "../components/BalanceSheet";
import { Term } from "../components/Term";
import { GuideBar } from "../components/GuideBar";
import { DeskCat } from "../components/PixelSprite";
import { CountUp, QuarterSplash, Typewriter } from "../components/Fx";
import { SoundPrompt } from "../components/SoundPrompt";
import { PredictModal, Surprise } from "../components/DeskExtras";
import { play } from "../sound";
import { SEASONS, SEASON_ICON, SEASON_NAME } from "../labels";

type Run = <T>(fn: () => Promise<T>) => Promise<T | undefined>;

export function Desk(props: {
  game: GameView;
  busy: boolean;
  run: Run;
  onUpdate: (g: GameView) => void;
  onShock: (s: Shock) => void;
  usage: Usage;
  onUsage: (u: Partial<Usage>) => void;
}) {
  const g = props.game;
  // The sliders are this quarter's trades: they start at zero and add to the positions carried in from
  // earlier quarters (g.action). The engine works with the resulting positions.
  const pos = g.action;
  const deltasFrom = (a: Action | null | undefined): Deltas =>
    Object.fromEntries(LEVER_KEYS.map((k) => [k, a ? Math.round((a[k] - pos[k]) * 100) / 100 : 0])) as Deltas;
  const termsFrom = (a: Action | null | undefined): Terms =>
    ({ collateralized: (a ?? pos).collateralized, dealers: (a ?? pos).dealers, accept_prt: a?.accept_prt ?? null });
  const [delta, setDelta] = useState<Deltas>(() => deltasFrom(g.pending));
  const [terms, setTerms] = useState<Terms>(() => termsFrom(g.pending));
  const draft: Action = useMemo(() => ({
    ...pos, ...terms,
    ...Object.fromEntries(LEVER_KEYS.map((k) => [k, clamp(Math.round((pos[k] + delta[k]) * 100) / 100, LEVERS[k].min, LEVERS[k].max)])),
  }), [pos, terms, delta]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const offersPrt = !!g.card?.offers_prt_deal && !g.prt_decided;
  const firstQuarter = g.quarter === 1 && g.history.length === 0;
  const [guide, setGuide] = useState<number>(() => {
    try { return localStorage.getItem("riskdesk-guide-hidden") ? -1 : 0; } catch { return 0; }
  });
  const showGuide = firstQuarter && guide >= 0;
  const focus = (n: number) => (showGuide && guide === n ? " guide-focus" : "");
  useEffect(() => {
    if (showGuide && guide === 2 && g.pending) setGuide(3);
  }, [g.pending]); // eslint-disable-line react-hooks/exhaustive-deps
  const hideGuide = () => {
    setGuide(-1);
    try { localStorage.setItem("riskdesk-guide-hidden", "1"); } catch { /* private mode */ }
  };

  useEffect(() => {
    setDelta(deltasFrom(g.pending));
    setTerms(termsFrom(g.pending));
  }, [g.id, g.quarter]); // eslint-disable-line react-hooks/exhaustive-deps

  // live preview of the ticket (debounced)
  useEffect(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      api.preview(g.id, draft).then(setPreview).catch(() => setPreview(null));
    }, 200);
    return () => window.clearTimeout(timer.current);
  }, [draft, g.id]);

  const set = <K extends keyof Terms>(k: K, v: Terms[K]) => setTerms((t) => ({ ...t, [k]: v }));
  const signed = !!g.pending && LEVER_KEYS.every((k) => Math.abs(g.pending![k] - draft[k]) < 1e-6)
    && g.pending.collateralized === draft.collateralized && g.pending.dealers === draft.dealers
    && (g.pending.accept_prt ?? null) === (draft.accept_prt ?? null);
  const needsPrt = offersPrt && draft.accept_prt === null;
  const [predicting, setPredicting] = useState(false);
  const isOpen = (k: string) => !g.unlocked || g.unlocked.includes(k === "counterparty" ? "collateralized" : k);
  const isNew = (k: string) => !!g.new_unlocks?.includes(k === "counterparty" ? "collateralized" : k);
  const boss = !!g.card?.boss;
  const [clock, setClock] = useState(180);
  useEffect(() => {  // the boss round: a siren and a (cosmetic) countdown to the market open
    if (!boss) return;
    const s = window.setTimeout(() => play("alarm"), 1200);
    const t = window.setInterval(() => setClock((c) => Math.max(0, c - 1)), 1000);
    return () => { clearTimeout(s); clearInterval(t); };
  }, [boss, g.id]);
  const Intro = ({ k }: { k: string }) => {
    const it = UNLOCK_INTRO[k];
    return isNew(k) && it ? (
      <div className="unlock-intro"><PixelSprite name={it.face} size={36} title={it.who} /><span><b>{it.who}:</b> {it.line}</span></div>
    ) : null;
  };
  const Locked = ({ label, k }: { label: string; k: string }) => (
    <div className="lever locked"><span className="lock">🔒</span> {label} <span className="muted">unlocks in Q{UNLOCK_Q[k]}</span></div>
  );
  const endQuarter = async (prediction: string | null) => {
    setPredicting(false);
    const s = await props.run(() => api.advance(g.id, prediction));
    if (s) props.onShock(s);
  };
  const worst = (st: Record<string, string>) =>
    (st.capital === "red" || st.liquidity === "red" ? "red" : st.capital === "amber" || st.liquidity === "amber" ? "amber" : "green") as "red" | "amber" | "green";

  return (
    <section className="desk">
      {g.card && <QuarterSplash id={g.id} quarter={g.card.quarter} of={g.n_quarters} boss={!!g.card.boss} title={g.card.title} era={g.card.era} />}
      {showGuide && <GuideBar step={guide} onNext={() => setGuide((x) => x + 1)} onHide={hideGuide} />}
      {g.card && <Surprise id={g.id} quarter={g.card.quarter} rule={g.card.rule ?? undefined} />}
      <SoundPrompt />
      {predicting && <PredictModal quarter={g.quarter} onPick={(p) => endQuarter(p)} onCancel={() => setPredicting(false)} />}
      <div className="desk-dash">
        <div className="panel">
          <div className="dash-head">
            <h3>Risk dashboard</h3>
            <DeskCat status={worst((preview?.after ?? g.dashboard).status)} size={56} boss={boss} />
          </div>
          {preview && !signed && <div className="small muted dash-note">→ shows the effect of your draft ticket</div>}
          <Meters dashboard={g.dashboard} after={preview?.after} />
        </div>
      </div>

      <div className="desk-mid">
        {g.card && (
          <div className={`panel wire${focus(0)}${g.card.boss ? " boss-wire" : ""}`}>
            <div className="wire-tag">NEWS WIRE · Q{g.card.quarter} · {SEASON_ICON[SEASONS[g.card.quarter]]} {SEASON_NAME[SEASONS[g.card.quarter]].toUpperCase()}{g.card.boss && <span className="boss-tag">⚠ BOSS ROUND · FINAL QUARTER</span>}</div>
            <h2>{g.card.title}</h2>
            <p className="wire-text"><span className="new-tag">NEW</span> <Typewriter text={g.card.signal_text} /></p>
          </div>
        )}

        <div className={focus(1).trim()}>
        <ChatPanel onAnswered={() => { if (showGuide && guide <= 1) setGuide(2); }} gameId={g.id} quarter={g.quarter} chat={g.chat} mode={g.agent_mode} demo={g.demo} usage={props.usage} onUsage={props.onUsage}
          onLoadTicket={(a) => { setDelta(deltasFrom(a)); setTerms({ ...termsFrom(a), accept_prt: offersPrt ? a.accept_prt ?? null : null }); }} />
        </div>
      </div>

      <div className="desk-right">
        <div className={`panel ticket${focus(2)}${focus(3)}`}>
          <h3><Term k="ticket_help" text={TICKET_TIP}>Trade ticket · Q{g.quarter}</Term></h3>
          {g.card?.rule && <div className="rule-banner"><b>⚡ RULE CHANGE</b> {g.card.rule}</div>}
          {boss && <div className="boss-banner">🚨 BOSS ROUND: this is the ticket that matters.</div>}
          {g.quarter > 1 && (
            <div className="holdings"><b>Fresh ticket.</b> Last quarter's swaps and puts were cash-settled when it ended. Your book now: cash {fmtNum(pos.cash_buffer_pct)}% of assets, collateral {pos.collateralized ? "on" : "off"}, {pos.dealers} dealer{pos.dealers === 3 ? "s" : ""}. <span className="muted">Each slider is a trade from here.</span></div>
          )}
          {LEVER_KEYS.map((k) => {
            const L = LEVERS[k];
            // the trade can take the position exactly to the lever's limits; in between it snaps to the step
            const lo = Math.round((L.min - pos[k]) * 100) / 100;
            const hi = Math.round((L.max - pos[k]) * 100) / 100;
            const snap = (v: number) => (v >= hi - L.step / 2 ? hi : v <= lo + L.step / 2 ? lo : Math.round(v / L.step) * L.step);
            const d = delta[k];
            const zeroAt = hi > lo ? (100 * -lo) / (hi - lo) : 50;
            if (!isOpen(k)) return <Locked key={k} label={L.label} k={k} />;
            return (
              <div className={`lever ${isNew(k) ? "new-lever" : ""}`} key={k}>
                {isNew(k) && <span className="new-badge">NEW</span>}
                <Intro k={k} />
                <div className="lever-head">
                  <label htmlFor={k}><Term k={L.term} text={L.tip}>{L.label}</Term></label>
                  <span className="lever-val">{d > 0 ? "+" : d < 0 ? "−" : ""}{fmtNum(Math.abs(d))}{L.unit}</span>
                </div>
                <div className="slider-wrap">
                  <span className="now-tick" style={{ left: `${zeroAt}%` }} title="What you hold now" />
                  <input id={k} type="range" min={lo} max={hi} step="any" value={d}
                    onChange={(e) => {
                      const v = snap(Number(e.target.value));
                      if (Math.floor(v / (L.step * 2)) !== Math.floor(d / (L.step * 2))) play("click");
                      setDelta((x) => ({ ...x, [k]: v }));
                    }} />
                </div>
                {k === "rate_hedge_pct" && (
                  <div className="rate-ends"><span>◀ pay fixed: gains if rates rise</span><span>receive fixed: gains if rates fall ▶</span></div>
                )}
                <div className="lever-pos">holding {fmtNum(pos[k])}{L.unit}{d !== 0 && <> → <b>{fmtNum(draft[k])}{L.unit}</b></>}</div>
              </div>
            );
          })}

          {!isOpen("counterparty") ? <Locked label="Counterparty terms" k="counterparty" /> : (
          <div className={`lever ${isNew("counterparty") ? "new-lever" : ""}`}>
            {isNew("counterparty") && <span className="new-badge">NEW</span>}
            <Intro k="counterparty" />
            <div className="lever-head"><label><Term k="collateral" text={COUNTERPARTY_TIP}>Counterparty terms</Term></label></div>
            <div className="toggle-row">
              <label><input type="checkbox" checked={draft.collateralized} onChange={(e) => set("collateralized", e.target.checked)} /> Daily collateral</label>
              <label>
                Dealers{" "}
                <select value={draft.dealers} onChange={(e) => set("dealers", Number(e.target.value) as 1 | 3)}>
                  <option value={1}>1 dealer</option>
                  <option value={3}>3 dealers</option>
                </select>
              </label>
            </div>
          </div>
          )}

          {offersPrt && (
            <div className="lever prt">
              <div className="lever-head"><label><Term k="pension_risk_transfer">Pension deal on offer</Term></label></div>
              <div className="small">A manufacturer wants to transfer its pension plan to you: long liabilities worth about 3% of your balance sheet, with premium and a 2% profit margin. It grows the business but uses capital.</div>
              <div className="toggle-row">
                <button className={draft.accept_prt === true ? "chip on" : "chip"} onClick={() => set("accept_prt", true)}>Accept</button>
                <button className={draft.accept_prt === false ? "chip on" : "chip"} onClick={() => set("accept_prt", false)}>Decline</button>
              </div>
            </div>
          )}

          {preview && (
            <div className="cost-meter">
              <div><span className="coin" aria-hidden>🪙</span> Hedges cost <b><CountUp value={preview.hedge_cost_per_quarter_usd_bn * 1000} format={(v) => `$${Math.round(v)}mn`} ms={400} /></b> a quarter</div>
              <div className="muted">Investment income less costs <b>${(preview.carry_per_quarter_usd_bn * 1000).toFixed(0)}mn</b></div>
            </div>
          )}

          <div className="ticket-buttons">
            <div className="btn-col">
            <button className="primary" disabled={props.busy || signed || needsPrt}
              onClick={async () => {
                const r = await props.run(() => api.commit(g.id, draft));
                if (r) { play("register"); props.onUpdate(r.view); }
              }}>
              {signed ? "Ticket signed ✓" : needsPrt ? "Decide on the pension deal" : "Sign trade ticket"}
            </button>
            <span className="btn-note">Locks in your trades. You can still ask the team before ending the quarter.</span>
            </div>
            <div className="btn-col">
            <button className="gold-btn" disabled={props.busy || (!signed && !!g.pending) || needsPrt}
              onClick={() => setPredicting(true)}>
              End Q{g.quarter} →
            </button>
            <span className="btn-note">{boss ? (clock > 0 ? <b className="countdown">Market opens in {Math.floor(clock / 60)}:{String(clock % 60).padStart(2, "0")}</b> : <b className="countdown">The market is open.</b>) : "The market moves. No going back."}</span>
            </div>
          </div>
          {!g.pending && <div className="small muted">No ticket signed yet: ending the quarter keeps your current positions.</div>}
          {g.pending && !signed && <div className="small warn">You changed the ticket after signing. Sign again to use the new trades.</div>}
        </div>
        <div className="panel cost-box">
          <h3>AI usage so far</h3>
          <div className="cost-figures">
            <div><b>{(props.usage.tokens.input + props.usage.tokens.output).toLocaleString()}</b><span>tokens</span></div>
            <div><b>${props.usage.spend_usd.toFixed(4)}</b><span>model cost</span></div>
          </div>
        </div>
      </div>

      <div className="desk-below">
        <details className="panel bs-details">
          <summary><h3>Balance sheet {preview && !signed && <span className="muted small">(after your draft ticket)</span>}</h3></summary>
          <BalanceSheetPanel dashboard={preview?.after ?? g.dashboard} compact />
        </details>
        {g.history.length > 0 && (
          <div className="panel">
            <h3>Past quarters</h3>
            <table className="table">
              <thead>
                <tr><th>Q</th><th>Event</th><th>Surplus change</th><th title="Results score, 0 to 100: your trades against doing nothing and what a pro would do. Vera's explanation marks are separate.">Results score</th></tr>
              </thead>
              <tbody>
                {g.history.map((h) => (
                  <tr key={h.quarter}>
                    <td>{h.quarter}</td>
                    <td>{h.title}</td>
                    <td className={h.change < 0 ? "neg" : "pos"}>{h.change >= 0 ? "+" : ""}{h.change.toFixed(2)}bn</td>
                    <td>{h.score ?? "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
