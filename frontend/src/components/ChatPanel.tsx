import { useEffect, useRef, useState } from "react";
import { api, askStream, type Action, type AgentEvent, type AgentMode, type ChatMsg, type Colleague, type SubAnswer, type Ticket, type Usage } from "../api";

type Turn = {
  role: "user" | "agent";
  text: string;
  agent?: string;
  agentName?: string;
  trace: AgentEvent[];
  subs: SubAnswer[];
  pending?: boolean;
  stopped?: string | null;
  ticket?: Ticket | null;
};

const SAMPLES = [
  "What is our biggest risk right now?",
  "Should we sell some junk and BBB bonds and buy government bonds?",
  "What happens to us if rates fall 1%?",
  "Should we hedge more of the stock-market guarantees?",
];

export const CAST: Record<string, { name: string; role: string; color: string }> = {
  solo: { name: "Dr. Amara Okafor", role: "CRO · Solo", color: "#001F5B" },
  cro: { name: "Dr. Amara Okafor", role: "Chief Risk Officer", color: "#001F5B" },
  actuary: { name: "Walt Brennan", role: "Actuary", color: "#537D93" },
  portfolio_manager: { name: "Priya Raman", role: "Portfolio Manager", color: "#B88600" },
  trader: { name: "Teo Vargas", role: "Trader", color: "#007AC1" },
  system: { name: "System", role: "", color: "#939598" },
};

function fromHistory(chat: ChatMsg[]): Turn[] {
  return chat.map((m) => ({
    role: m.role, text: m.text, agent: m.agent, agentName: m.agent_name, trace: [], subs: m.subs ?? [],
    stopped: m.stopped ?? null, ticket: m.proposed_ticket ?? null,
  }));
}

function short(v: unknown): string {
  if (v && typeof v === "object") {
    const entries = Object.entries(v as Record<string, unknown>).filter(([, x]) => typeof x !== "object").slice(0, 4);
    return entries.map(([k, x]) => `${k.replace(/_/g, " ")}: ${x}`).join(" · ");
  }
  return String(v);
}

function who(agent: string) {
  return CAST[agent]?.name.split(" ").slice(-2).join(" ") ?? agent;
}

function TraceLine({ e }: { e: AgentEvent }) {
  const tag = <span className="tr-agent" style={{ color: CAST[e.agent]?.color }}>{who(e.agent).split(" ")[0]}</span>;
  if (e.type === "delegation" && e.detail.to)
    return <li className="tr-deleg">{tag} → asked <b>{CAST[e.detail.to]?.name}</b>: <span className="muted">{e.detail.task}</span></li>;
  if (e.type === "delegation" && e.detail.from)
    return <li className="tr-deleg">{tag} → answered Amara</li>;
  if (e.type === "tool_call" && !String(e.detail.tool).startsWith("ask_"))
    return <li className="tr-call">{tag} called <code>{e.detail.tool}</code>{Object.keys(e.detail.args ?? {}).length ? <span className="muted"> {JSON.stringify(e.detail.args)}</span> : null}</li>;
  if (e.type === "tool_result")
    return <li className="tr-result">{tag} ← <code>{e.detail.tool}</code> <span className="muted">{short(e.detail.result)}</span></li>;
  if (e.type === "spend")
    return <li className="tr-spend">{tag} model call · {e.input_tokens.toLocaleString()} in ({e.cached_tokens.toLocaleString()} cached) · {e.output_tokens.toLocaleString()} out · ${e.cost_usd.toFixed(5)}</li>;
  if (e.type === "blocked" || e.type === "stop" || e.type === "error")
    return <li className="tr-blocked">⛔ {e.type}: {e.detail.reason ?? ""} {e.detail.message ?? ""}</li>;
  return null;
}

export function ChatPanel(props: {
  gameId: string;
  chat: ChatMsg[];
  mode: AgentMode;
  usage: Usage;
  onUsage: (u: Partial<Usage>) => void;
  onLoadTicket: (a: Action) => void;
}) {
  const [turns, setTurns] = useState<Turn[]>(() => fromHistory(props.chat));
  const [mode, setMode] = useState<AgentMode>(props.mode);
  const [to, setTo] = useState<Colleague>("team");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [openTrace, setOpenTrace] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTurns(fromHistory(props.chat));
    setMode(props.mode);
  }, [props.gameId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    // newer browsers return a Promise from scrollIntoView; never hand it back to React as a cleanup
    void endRef.current?.scrollIntoView({ block: "nearest" });
  }, [turns]);

  async function switchMode(m: AgentMode) {
    if (m === mode || busy) return;
    const r = await api.setMode(props.gameId, m);
    setMode(r.agent_mode);
    setTo("team");
  }

  async function send(q: string) {
    const msg = q.trim();
    if (!msg || busy) return;
    setText("");
    setBusy(true);
    const lead = mode === "solo" ? "solo" : to === "team" ? "cro" : to;
    let idx = -1;
    setTurns((t) => {
      idx = t.length + 1;
      return [...t, { role: "user", text: msg, trace: [], subs: [] },
        { role: "agent", text: "", agent: lead, agentName: CAST[lead].name, trace: [], subs: [], pending: true }];
    });
    setOpenTrace(null);
    const update = (fn: (t: Turn) => Turn) => setTurns((all) => all.map((t, i) => (i === all.length - 1 ? fn(t) : t)));
    try {
      await askStream(props.gameId, msg, (e) => {
        if (e.type === "usage") props.onUsage(e.detail);
        else if (e.type === "reply")
          update((t) => ({ ...t, text: e.detail.text, pending: false, stopped: e.detail.stopped, ticket: e.detail.proposed_ticket,
            agent: e.agent, agentName: e.agent_name ?? t.agentName, subs: e.detail.subs ?? t.subs }));
        else if (e.type === "delegation" && e.detail.from)
          update((t) => ({ ...t, trace: [...t.trace, e], subs: [...t.subs, { agent: e.detail.from, agent_name: e.detail.from_name, text: e.detail.answer }] }));
        else if (e.type !== "start") update((t) => ({ ...t, trace: [...t.trace, e] }));
      }, mode === "team" ? to : undefined);
    } catch (err) {
      update((t) => ({ ...t, text: `Connection problem: ${err instanceof Error ? err.message : String(err)}`, pending: false }));
    } finally {
      setBusy(false);
      setOpenTrace(idx);
    }
  }

  const blocked = props.usage.blocked;
  const delegations = (t: Turn) => t.trace.filter((e) => e.type === "delegation" && e.detail.to).length;

  return (
    <div className="panel chat">
      <div className="chat-head">
        <h3>Ask your {mode === "team" ? "team" : "colleague"}</h3>
        <div className="seg" role="group" aria-label="Agent mode">
          <button className={mode === "team" ? "on" : ""} onClick={() => switchMode("team")} disabled={busy}>Team</button>
          <button className={mode === "solo" ? "on" : ""} onClick={() => switchMode("solo")} disabled={busy}>Solo</button>
        </div>
      </div>
      {mode === "team" ? (
        <div className="cast-row">
          {(["team", "actuary", "portfolio_manager", "trader"] as Colleague[]).map((c) => {
            const k = c === "team" ? "cro" : c;
            return (
              <button key={c} className={`cast-chip ${to === c ? "on" : ""}`} style={{ borderColor: CAST[k].color }}
                onClick={() => setTo(c)} disabled={busy} title={c === "team" ? "Amara routes your question to the right specialists" : `Ask ${CAST[k].name} directly`}>
                <span className="cast-dot" style={{ background: CAST[k].color }} />
                {c === "team" ? "Amara (routes to team)" : `${CAST[k].name.split(" ")[0]} · ${CAST[k].role}`}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="small muted">Solo mode: one agent, Dr. Amara Okafor, holds every tool. Switch to Team to hear specialists with different views.</div>
      )}
      {blocked && <div className="banner warn-banner">Budget cap reached: the AI colleagues are offline for this session. The game continues.</div>}
      <div className="chat-log">
        {turns.length === 0 && <div className="muted small">Ask anything about this company's risks. Every number in a reply comes from the engine's tools; you can see each tool call and which colleague made it.</div>}
        {turns.map((t, i) => (
          <div key={i} className={`msg ${t.role}`} style={t.role === "agent" ? { borderLeftColor: CAST[t.agent ?? "system"]?.color } : undefined}>
            {t.role === "agent" && <div className="msg-name" style={{ color: CAST[t.agent ?? "system"]?.color }}>{t.agentName ?? "Colleague"}</div>}
            {t.subs.length > 0 && (
              <div className="subs">
                {t.subs.map((s, k) => (
                  <div key={k} className="sub-msg" style={{ borderLeftColor: CAST[s.agent]?.color }}>
                    <div className="msg-name" style={{ color: CAST[s.agent]?.color }}>{s.agent_name}</div>
                    <div className="msg-text">{s.text}</div>
                  </div>
                ))}
              </div>
            )}
            <div className="msg-text">{t.pending && !t.text ? <span className="spinner" aria-label="thinking" /> : t.text}</div>
            {t.role === "agent" && t.trace.length > 0 && (
              <div className="trace">
                <button className="link" onClick={() => setOpenTrace(openTrace === i ? null : i)}>
                  {openTrace === i || t.pending ? "▾" : "▸"} {delegations(t) ? `${delegations(t)} delegations · ` : ""}
                  {t.trace.filter((e) => e.type === "tool_call" && !String(e.detail.tool).startsWith("ask_")).length} tool calls ·{" "}
                  {t.trace.filter((e) => e.type === "spend").length} model calls · $
                  {t.trace.reduce((s, e) => s + (e.type === "spend" ? e.cost_usd : 0), 0).toFixed(5)}
                </button>
                {(openTrace === i || t.pending) && <ul className="trace-list">{t.trace.map((e, k) => <TraceLine key={k} e={e} />)}</ul>}
              </div>
            )}
            {t.ticket && (
              <div className="proposed">
                <b>Proposed ticket</b> <span className="small muted">{t.ticket.by}: {t.ticket.rationale}</span>
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
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about rates, credit, liquidity, hedges…" maxLength={2000} aria-label="Question for your colleagues" />
        <button className="primary" disabled={busy || !text.trim()}>{busy ? "Thinking…" : "Ask"}</button>
      </form>
    </div>
  );
}
