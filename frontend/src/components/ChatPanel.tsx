import { useEffect, useRef, useState } from "react";
import { PixelSprite, spriteFor } from "./PixelSprite";
import { play } from "../sound";
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
  runId?: string;
  flagged?: boolean;
};

const SAMPLES = [
  "What is our biggest risk right now?",
  "Should we sell some junk and BBB bonds and buy government bonds?",
  "What happens to us if rates fall 1%?",
  "Should we hedge more of the stock-market guarantees?",
];

export const CAST: Record<string, { name: string; short: string; role: string; color: string }> = {
  solo: { name: "Vera Atrisk", short: "Vera", role: "CRO · Solo", color: "#001F5B" },
  cro: { name: "Vera Atrisk", short: "Vera", role: "Chief Risk Officer", color: "#001F5B" },
  actuary: { name: "Morty Tables", short: "Morty", role: "Actuary", color: "#537D93" },
  portfolio_manager: { name: "Bonnie Yields", short: "Bonnie", role: "Portfolio Manager", color: "#B88600" },
  trader: { name: "Swap Dogg", short: "Swap Dogg", role: "Trader", color: "#007AC1" },
  system: { name: "System", short: "System", role: "", color: "#939598" },
};

function fromHistory(chat: ChatMsg[]): Turn[] {
  return chat.map((m) => ({
    role: m.role, text: m.text, agent: m.agent, agentName: m.agent_name, trace: [], subs: m.subs ?? [],
    stopped: m.stopped ?? null, ticket: m.proposed_ticket ?? null, runId: m.run_id,
  }));
}

function short(v: unknown): string {
  if (v && typeof v === "object") {
    const entries = Object.entries(v as Record<string, unknown>).filter(([, x]) => typeof x !== "object").slice(0, 4);
    return entries.map(([k, x]) => `${k.replace(/_/g, " ")}: ${x}`).join(" · ");
  }
  return String(v);
}

/** The short name the cast goes by: Vera, Morty, Bonnie, Swap Dogg. */
export function nick(agent: string | undefined): string {
  return (agent && CAST[agent]?.short) || agent || "A colleague";
}

/** Who is working right now in a pending turn, and on what: drives the typing line and the cast chips. */
function activity(t: Turn): { agent: string; doing: string } {
  let agent = t.agent ?? "cro";
  let doing = "typing";
  for (const e of t.trace) {
    if (e.type === "delegation" && e.detail.to) { agent = e.detail.to; doing = "reading the question"; }
    else if (e.type === "delegation" && e.detail.from) { agent = t.agent ?? "cro"; doing = `reading ${nick(e.detail.from)}'s answer`; }
    else if (e.type === "tool_call" && !String(e.detail.tool).startsWith("ask_")) {
      agent = e.agent;
      doing = `checking the ${String(e.detail.tool).replace(/^get_/, "").replace(/_/g, " ")}`;
    } else if (e.type === "spend") { agent = e.agent; doing = "typing"; }
  }
  return { agent, doing };
}

function TypingLine({ t }: { t: Turn }) {
  const a = activity(t);
  const face = spriteFor(a.agent);
  return (
    <div className="typing" aria-live="polite">
      {face && <span className="typing-face"><PixelSprite name={face} size={24} /></span>}
      <span><b>{nick(a.agent)}</b> is {a.doing}</span>
      <span className="dots3"><i /><i /><i /></span>
    </div>
  );
}

/** Small factual reactions under a finished reply. */
function Reactions({ t }: { t: Turn }) {
  const chips: string[] = [];
  const n = new Set(t.trace.filter((e) => e.type === "delegation" && e.detail.to).map((e) => e.detail.to)).size;
  if (n) chips.push(`🤝 ${n} colleague${n > 1 ? "s" : ""} consulted`);
  const tools = t.trace.filter((e) => e.type === "tool_call" && !String(e.detail.tool).startsWith("ask_")).length;
  if (tools) chips.push(`📊 ${tools} engine check${tools > 1 ? "s" : ""}`);
  if (t.ticket) chips.push("📝 drafted a ticket for you");
  if (t.stopped) chips.push("⛔ stopped early");
  if (!chips.length) return null;
  return <div className="reactions">{chips.map((c, i) => <span key={i} className="reaction" style={{ animationDelay: `${i * 0.12}s` }}>{c}</span>)}</div>;
}

function TraceLine({ e }: { e: AgentEvent }) {
  const tag = <span className="tr-agent" style={{ color: CAST[e.agent]?.color }}>{nick(e.agent)}</span>;
  if (e.type === "delegation" && e.detail.to)
    return <li className="tr-deleg">{tag} → asked <b>{CAST[e.detail.to]?.name}</b>: <span className="muted">{e.detail.task}</span></li>;
  if (e.type === "delegation" && e.detail.from)
    return <li className="tr-deleg">{tag} → answered Vera</li>;
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
  onAnswered?: () => void;
  demo?: boolean;
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
    setMode(props.mode);
  }, [props.mode]);
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
    setTurns((t) => [...t, { role: "user", text: msg, trace: [], subs: [] },
      { role: "agent", text: "", agent: lead, agentName: CAST[lead].name, trace: [], subs: [], pending: true }]);
    setOpenTrace(null);
    const update = (fn: (t: Turn) => Turn) => setTurns((all) => all.map((t, i) => (i === all.length - 1 ? fn(t) : t)));
    try {
      await askStream(props.gameId, msg, (e) => {
        if (e.type === "usage") props.onUsage(e.detail);
        else if (e.type === "reply") {
          play("click");
          update((t) => ({ ...t, text: e.detail.text, pending: false, stopped: e.detail.stopped, ticket: e.detail.proposed_ticket,
            agent: e.agent, agentName: e.agent_name ?? t.agentName, subs: e.detail.subs ?? t.subs, runId: e.run_id }));
        }
        else if (e.type === "delegation" && e.detail.from)
          update((t) => ({ ...t, trace: [...t.trace, e], subs: [...t.subs, { agent: e.detail.from, agent_name: e.detail.from_name, text: e.detail.answer }] }));
        else if (e.type !== "start") update((t) => ({ ...t, trace: [...t.trace, e] }));
      }, mode === "team" ? to : undefined);
    } catch (err) {
      update((t) => ({ ...t, text: `Connection problem: ${err instanceof Error ? err.message : String(err)}`, pending: false }));
    } finally {
      setBusy(false);
      props.onAnswered?.();
    }
  }

  const blocked = props.usage.blocked;
  const live = turns.length && turns[turns.length - 1].pending ? turns[turns.length - 1] : null;
  const liveAgent = live ? activity(live).agent : null;
  const answered = new Set(live ? live.subs.map((s) => s.agent) : []);
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
              <button key={c} className={`cast-chip ${to === c ? "on" : ""} ${liveAgent === k ? "working" : ""} ${answered.has(k) ? "answered" : ""}`} style={{ borderColor: CAST[k].color }}
                onClick={() => setTo(c)} disabled={busy} title={c === "team" ? "Vera routes your question to the right specialists" : `Ask ${CAST[k].name} directly`}>
                <PixelSprite name={spriteFor(k)!} size={22} className="chip-face" />
                {c === "team" ? "Vera (routes to team)" : `${CAST[k].short} · ${CAST[k].role}`}
                {answered.has(k) && <span className="chip-check">✓</span>}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="small muted">Solo mode: one agent, Vera Atrisk, holds every tool. Switch to Team to hear specialists with different views.</div>
      )}
      {blocked && <div className="banner warn-banner">Budget cap reached: the AI colleagues are offline for this session. The game continues.</div>}
      <div className="chat-log">
        {turns.length === 0 && <div className="muted small">Type your own question about this company's risks. Every number in a reply comes from the engine's tools; open Chat detail below to see who did what.</div>}
        {turns.map((t, i) => (
          <div key={i} className={`msg ${t.role}`} style={t.role === "agent" ? { borderLeftColor: CAST[t.agent ?? "system"]?.color } : undefined}>
            {t.role === "agent" && (
              <div className="msg-name" style={{ color: CAST[t.agent ?? "system"]?.color }}>
                {spriteFor(t.agent) && <PixelSprite name={spriteFor(t.agent, t.stopped ? "concerned" : t.ticket ? "pleased" : "neutral")!} size={28} className={`msg-face ${t.pending ? "" : "arrive"}`} />}
                {t.agentName ?? "Colleague"}
              </div>
            )}
            <div className="msg-text">{t.pending && !t.text ? <TypingLine t={t} /> : t.text}</div>
            {t.role === "agent" && !t.pending && <Reactions t={t} />}
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
      {props.demo && (
        <div className="samples">
          <span className="small muted">Demo questions:</span>
          {SAMPLES.map((s) => <button key={s} className="chip" disabled={busy} onClick={() => send(s)}>{s}</button>)}
        </div>
      )}
      <form className="ask-row" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about rates, credit, liquidity, hedges…" maxLength={2000} aria-label="Question for your colleagues" />
        <button className="primary" disabled={busy || !text.trim()}>{busy ? "Thinking…" : "Ask"}</button>
      </form>
      {turns.some((t) => t.role === "agent" && (t.trace.length > 0 || t.subs.length > 0)) && (
        <details className="chat-detail">
          <summary>Show chat detail <span className="muted small">· specialist answers, tool calls and costs</span></summary>
          {turns.map((t, i) => t.role !== "agent" || (t.trace.length === 0 && t.subs.length === 0) ? null : (
            <div key={i} className="detail-turn">
              <div className="detail-q">Q: {turns[i - 1]?.role === "user" ? turns[i - 1].text : "(question)"}</div>
              {t.subs.length > 0 && (
                <div className="subs">
                  {t.subs.map((s, k) => (
                    <div key={k} className="sub-msg" style={{ borderLeftColor: CAST[s.agent]?.color }}>
                      <div className="msg-name" style={{ color: CAST[s.agent]?.color }}>
                        {spriteFor(s.agent) && <PixelSprite name={spriteFor(s.agent)!} size={22} className="msg-face" />}
                        {s.agent_name}
                      </div>
                      <div className="msg-text">{s.text}</div>
                    </div>
                  ))}
                </div>
              )}
              {t.trace.length > 0 && (
                <div className="trace">
                  <button className="link" onClick={() => setOpenTrace(openTrace === i ? null : i)}>
                    {openTrace === i ? "▾" : "▸"} {delegations(t) ? `${delegations(t)} delegations · ` : ""}
                    {t.trace.filter((e) => e.type === "tool_call" && !String(e.detail.tool).startsWith("ask_")).length} tool calls ·{" "}
                    {t.trace.filter((e) => e.type === "spend").length} model calls · $
                    {t.trace.reduce((s, e) => s + (e.type === "spend" ? e.cost_usd : 0), 0).toFixed(5)}
                  </button>
                  {openTrace === i && <ul className="trace-list">{t.trace.map((e, k) => <TraceLine key={k} e={e} />)}</ul>}
                </div>
              )}
              {!t.pending && t.runId && t.agent !== "system" && (
                <button className="link flag-btn" disabled={t.flagged}
                  onClick={async () => {
                    const note = window.prompt("What seems wrong in this reply? (optional)") ?? "";
                    await api.flag(t.runId!, props.gameId, note, t.text).catch(() => undefined);
                    setTurns((all) => all.map((x, k) => (k === i ? { ...x, flagged: true } : x)));
                  }}>
                  {t.flagged ? "⚑ Flagged for review, thank you" : "⚑ This reply seems wrong"}
                </button>
              )}
            </div>
          ))}
        </details>
      )}
    </div>
  );
}
