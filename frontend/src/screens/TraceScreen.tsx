import { useEffect, useState } from "react";
import type { AgentEvent, GameView } from "../api";
import { CAST } from "../components/ChatPanel";

type Usage = { agent: string; input_tokens: number; cache_read_tokens: number; output_tokens: number; cost_usd: number; ts: number };

function summarize(e: AgentEvent): string {
  const d = e.detail ?? {};
  switch (e.type) {
    case "delegation": return d.to ? `asked ${d.to_name}: ${d.task}` : `answered: ${String(d.answer).slice(0, 140)}`;
    case "tool_call": return `${d.tool}(${Object.keys(d.args ?? {}).length ? JSON.stringify(d.args) : ""})`;
    case "tool_result": return `${d.tool} → ${JSON.stringify(d.result).slice(0, 140)}`;
    case "reply": return String(d.text ?? "").slice(0, 180);
    case "blocked": case "stop": case "error": return `${d.reason ?? ""} ${d.message ?? ""}`;
    case "start": return String(d.question ?? d.prompt ?? "").slice(0, 160);
    default: return JSON.stringify(d).slice(0, 160);
  }
}

export function TraceScreen(props: { game: GameView; onBack: () => void }) {
  const [events, setEvents] = useState<AgentEvent[] | null>(null);
  const [usage, setUsage] = useState<Usage[]>([]);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    fetch(`/api/audit/${props.game.id}`).then((r) => r.json()).then((j) => { setEvents(j.events); setUsage(j.usage); });
  }, [props.game.id]);

  const shown = (events ?? []).filter((e) => e.type !== "usage" && (filter === "all" || e.type === filter));
  const total = usage.reduce((s, u) => s + u.cost_usd, 0);

  return (
    <section className="trace-screen">
      <div className="panel">
        <div className="lab-head">
          <div>
            <h1>Trace</h1>
            <p className="muted">The append-only audit trail for this session ({props.game.company}, seed {props.game.seed}). Every delegation, tool call, model call, block and reply, with API-reported tokens and cost.</p>
            <div className="small muted">{events?.length ?? 0} events · {usage.length} model calls · ${total.toFixed(5)}</div>
          </div>
          <div className="lab-actions">
            <select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter events">
              {["all", "delegation", "tool_call", "tool_result", "spend", "reply", "blocked"].map((f) => <option key={f}>{f}</option>)}
            </select>
            <button className="ghost" onClick={props.onBack}>← Back</button>
          </div>
        </div>
      </div>
      <div className="panel">
        {events === null ? <span className="spinner" /> : shown.length === 0 ? <p className="muted">No events yet: ask your colleagues a question.</p> : (
          <table className="table trace-table">
            <thead><tr><th>Time</th><th>Q</th><th>Who</th><th>Event</th><th>Detail</th><th className="num">Tokens in / cached / out</th><th className="num">Cost</th></tr></thead>
            <tbody>
              {shown.map((e, i) => (
                <tr key={i}>
                  <td className="small">{new Date(e.ts * 1000).toLocaleTimeString()}</td>
                  <td className="small">{(e as unknown as { quarter: number }).quarter}</td>
                  <td className="small" style={{ color: CAST[e.agent]?.color }}><b>{CAST[e.agent]?.short ?? e.agent}</b></td>
                  <td className="small"><code>{e.type}</code></td>
                  <td className="small">{summarize(e)}</td>
                  <td className="num small">{e.input_tokens ? `${e.input_tokens} / ${e.cached_tokens} / ${e.output_tokens}` : ""}</td>
                  <td className="num small">{e.cost_usd ? `$${e.cost_usd.toFixed(5)}` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
