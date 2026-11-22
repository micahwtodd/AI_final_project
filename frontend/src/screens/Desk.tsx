import { useEffect, useRef, useState } from "react";
import { api, type Action, type GameView, type Preview, type Shock, type Usage } from "../api";
import { ChatPanel } from "../components/ChatPanel";
import { LEVERS, type LeverKey } from "../labels";
import { Meters } from "../components/Meters";
import { BalanceSheetPanel } from "../components/BalanceSheet";
import { Term } from "../components/Term";
import { GuideBar } from "../components/GuideBar";
import { DeskCat } from "../components/PixelSprite";
import { QuarterSplash } from "../components/Fx";

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
  const [draft, setDraft] = useState<Action>(g.pending ?? { ...g.action, accept_prt: null });
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
    setDraft(g.pending ?? { ...g.action, accept_prt: null });
  }, [g.id, g.quarter]); // eslint-disable-line react-hooks/exhaustive-deps

  // live preview of the ticket (debounced)
  useEffect(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      api.preview(g.id, draft).then(setPreview).catch(() => setPreview(null));
    }, 200);
    return () => window.clearTimeout(timer.current);
  }, [draft, g.id]);

  const set = <K extends keyof Action>(k: K, v: Action[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const signed = !!g.pending && JSON.stringify(g.pending) === JSON.stringify(draft);
  const needsPrt = offersPrt && draft.accept_prt === null;

  return (
    <section className="desk">
      {g.card && <QuarterSplash id={g.id} quarter={g.card.quarter} title={g.card.title} era={g.card.era} />}
      {showGuide && <GuideBar step={guide} onNext={() => setGuide((x) => x + 1)} onHide={hideGuide} />}
      <div className="desk-left">
        {g.card && (
          <div className={`panel wire${focus(0)}`}>
            <div className="wire-tag">NEWS WIRE · Q{g.card.quarter}</div>
            <h2>{g.card.title}</h2>
            <p className="wire-text">{g.card.signal_text}</p>
            <p className="small muted">A hint, not a forecast. The market may move more, less, or not at all.</p>
          </div>
        )}

        <div className={focus(1).trim()}>
        <ChatPanel onAnswered={() => { if (showGuide && guide <= 1) setGuide(2); }} gameId={g.id} chat={g.chat} mode={g.agent_mode} usage={props.usage} onUsage={props.onUsage}
          onLoadTicket={(a) => setDraft({ ...a, accept_prt: offersPrt ? a.accept_prt : null })} />
        </div>

        <div className="panel">
          <div className="dash-head">
            <h3>Risk dashboard {preview && !signed && <span className="muted small">(→ shows the effect of your draft ticket)</span>}</h3>
            <DeskCat status={(preview?.after ?? g.dashboard).status.capital} />
          </div>
          <Meters dashboard={g.dashboard} after={preview?.after} />
        </div>

        <div className="panel">
          <h3>Balance sheet {preview && !signed && <span className="muted small">(after your draft ticket)</span>}</h3>
          <BalanceSheetPanel dashboard={preview?.after ?? g.dashboard} compact />
        </div>

        {g.history.length > 0 && (
          <div className="panel">
            <h3>Past quarters</h3>
            <table className="table">
              <thead>
                <tr><th>Q</th><th>Event</th><th>Surplus change</th><th>Score</th></tr>
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

      <div className="desk-right">
        <div className={`panel ticket${focus(2)}${focus(3)}`}>
          <h3>Trade ticket · Q{g.quarter}</h3>
          {(Object.keys(LEVERS) as LeverKey[]).map((k) => {
            const L = LEVERS[k];
            return (
              <div className="lever" key={k}>
                <div className="lever-head">
                  <label htmlFor={k}><Term k={L.term}>{L.label}</Term></label>
                  <span className="lever-val">{draft[k]}{L.unit}</span>
                </div>
                <input id={k} type="range" min={L.min} max={L.max} step={L.step} value={draft[k]}
                  onChange={(e) => set(k, Number(e.target.value))} />
                <div className="small muted">{L.help}</div>
              </div>
            );
          })}

          <div className="lever">
            <div className="lever-head"><label><Term k="collateral">Counterparty terms</Term></label></div>
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
            <div className="small muted">Collateral means dealers post cash daily; if one fails you lose little. It can also demand cash from you.</div>
          </div>

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
            <div className="cost-row small">
              Hedge cost per quarter <b>${preview.hedge_cost_per_quarter_usd_bn.toFixed(3)}bn</b> · Investment income
              less costs <b>${preview.carry_per_quarter_usd_bn.toFixed(3)}bn</b>
            </div>
          )}

          <div className="ticket-buttons">
            <button className="primary" disabled={props.busy || signed || needsPrt}
              onClick={async () => {
                const r = await props.run(() => api.commit(g.id, draft));
                if (r) props.onUpdate(r.view);
              }}>
              {signed ? "Ticket signed ✓" : needsPrt ? "Decide on the pension deal" : "Sign trade ticket"}
            </button>
            <button className="danger" disabled={props.busy || (!signed && !!g.pending) || needsPrt}
              onClick={async () => {
                const s = await props.run(() => api.advance(g.id));
                if (s) props.onShock(s);
              }}>
              End quarter Q{g.quarter} →
            </button>
          </div>
          {!g.pending && <div className="small muted">No ticket signed yet: ending the quarter keeps your current positions.</div>}
          {g.pending && !signed && <div className="small warn">You changed the ticket after signing. Sign again to use the new trades.</div>}
        </div>
      </div>
    </section>
  );
}
