import { useEffect, useRef, useState } from "react";
import { askStream, type Action, type AgentEvent, type ChatMsg, type Ticket, type Usage } from "../api";

type Turn = {
  role: "user" | "agent";
  text: string;
  agentName?: string;
  trace: AgentEvent[];
  pending?: boolean;
  stopped?: string | null;
  ticket?: Ticket | null;
};

const SAMPLES = [
  "What is our biggest risk right now?",
  "What happens to us if rates fall 1%?",
  "Explain our rate mismatch in plain words.",
  "What would it cost to hedge half the stock-market guarantees?",
];

function fromHistory(chat: ChatMsg[]): Turn[] {
  return chat.map((m) => ({
    role: m.role, text: m.text, agentName: m.agent_name, trace: [], stopped: m.stopped ?? null,
    ticket: m.proposed_ticket ?? null,
  }));
}

function short(v: unknown): string {
  if (v && typeof v === "object") {
    const entries = Object.entries(v as Record<string, unknown>).filter(([, x]) => typeof x !== "object").slice(0, 4);
    return entries.map(([k, x]) => `${k.replace(/_/g, " ")}: ${x}`).join(" · ");
  }
  return String(v);
}

function TraceLine({ e }: { e: AgentEvent }) {
  if (e.type === "tool_call")
    return <li className="tr-call">→ called <code>{e.detail.tool}</code>{Object.keys(e.detail.args ?? {}).length ? <span className="muted"> {JSON.stringify(e.detail.args)}</span> : null}</li>;
  if (e.type === "tool_result")
    return <li className="tr-result">← <code>{e.detail.tool}</code> <span className="muted">{short(e.detail.result)}</span></li>;
  if (e.type === "spend")
    return <li className="tr-spend">model call · {e.input_tokens.toLocaleString()} in ({e.cached_tokens.toLocaleString()} cached) · {e.output_tokens.toLocaleString()} out · ${e.cost_usd.toFixed(5)}</li>;
  if (e.type === "blocked" || e.type === "stop" || e.type === "error")
    return <li className="tr-blocked">⛔ {e.type}: {e.detail.reason ?? ""} {e.detail.message ?? ""}</li>;
  return null;
}

export function ChatPanel(props: {
  gameId: string;
  chat: ChatMsg[];
  usage: Usage;
  onUsage: (u: Partial<Usage>) => void;
  onLoadTicket: (a: Action) => void;
}) {
  const [turns, setTurns] = useState<Turn[]>(() => fromHistory(props.chat));
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [openTrace, setOpenTrace] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTurns(fromHistory(props.chat));
  }, [props.gameId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    // newer browsers return a Promise from scrollIntoView; never hand it back to React as a cleanup
    void endRef.current?.scrollIntoView({ block: "nearest" });
  }, [turns]);

  async function send(q: string) {
    const msg = q.trim();
    if (!msg || busy) return;
    setText("");
    setBusy(true);
    let idx = -1;
    setTurns((t) => {
      idx = t.length + 1;
      return [...t, { role: "user", text: msg, trace: [] }, { role: "agent", text: "", trace: [], pending: true, agentName: "Dr. Amara Okafor (Solo)" }];
    });
    setOpenTrace(null);
    const update = (fn: (t: Turn) => Turn) =>
      setTurns((all) => all.map((t, i) => (i === all.length - 1 ? fn(t) : t)));
    try {
      await askStream(props.gameId, msg, (e) => {
        if (e.type === "usage") props.onUsage(e.detail);
        else if (e.type === "reply")
          update((t) => ({ ...t, text: e.detail.text, pending: false, stopped: e.detail.stopped, ticket: e.detail.proposed_ticket, agentName: e.agent_name ?? t.agentName }));
        else update((t) => ({ ...t, trace: [...t.trace, e] }));
      });
    } catch (err) {
      update((t) => ({ ...t, text: `Connection problem: ${err instanceof Error ? err.message : String(err)}`, pending: false }));
    } finally {
      setBusy(false);
      setOpenTrace(idx);
    }
  }

  const blocked = props.usage.blocked;

  return (
    <div className="panel chat">
      <h3>Ask your colleague <span className="muted small">Solo mode: Dr. Amara Okafor, CRO</span></h3>
      {blocked && <div className="banner warn-banner">Budget cap reached: the AI colleagues are offline for this session. The game continues.</div>}
      <div className="chat-log">
        {turns.length === 0 && <div className="muted small">Ask anything about this company's risks. Every number in a reply comes from the engine's tools; you can see each tool call.</div>}
        {turns.map((t, i) => (
          <div key={i} className={`msg ${t.role}`}>
            {t.role === "agent" && <div className="msg-name">{t.agentName ?? "Colleague"}</div>}
            <div className="msg-text">{t.pending && !t.text ? <span className="spinner" aria-label="thinking" /> : t.text}</div>
            {t.role === "agent" && t.trace.length > 0 && (
              <div className="trace">
                <button className="link" onClick={() => setOpenTrace(openTrace === i ? null : i)}>
                  {openTrace === i || t.pending ? "▾" : "▸"} {t.trace.filter((e) => e.type === "tool_call").length} tool calls ·{" "}
                  {t.trace.filter((e) => e.type === "spend").length} model calls · $
                  {t.trace.reduce((s, e) => s + (e.type === "spend" ? e.cost_usd : 0), 0).toFixed(5)}
                </button>
                {(openTrace === i || t.pending) && <ul className="trace-list">{t.trace.map((e, k) => <TraceLine key={k} e={e} />)}</ul>}
              </div>
            )}
            {t.ticket && (
              <div className="proposed">
                <b>Proposed ticket</b> <span className="small muted">{t.ticket.rationale}</span>
                <button className="chip" onClick={() => props.onLoadTicket(t.ticket!.action)}>Load into my ticket</button>
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div className="samples">
        {SAMPLES.map((s) => <button key={s} className="chip" disabled={busy} onClick={() => send(s)}>{s}</button>)}
      </div>
      <form className="ask-row" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about rates, credit, liquidity, hedges…" maxLength={2000} aria-label="Question for your colleague" />
        <button className="primary" disabled={busy || !text.trim()}>{busy ? "Thinking…" : "Ask"}</button>
      </form>
    </div>
  );
}
