"""Agents. Every model call goes to gpt-6-luna, through Portkey or OpenAI.

Project 3: Solo mode (one agent in Amara's voice holding every read tool plus propose_trade),
a live event stream for the trace, per-call usage logging, and a hard budget cap.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ToolCallPart
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from backend import audit, tools
from backend.calibration import DISPLAY_NAMES
from backend.env import MODEL_NAME, REPO_DIR, load_env, provider_config, redact
from backend.pricing import cost_usd

PROMPTS = REPO_DIR / "backend" / "prompts"
REQUEST_LIMIT = 6
HISTORY_RUNS = 3  # short-term memory: the last few question/answer exchanges

AGENT_NAMES = {"solo": "Dr. Amara Okafor (Solo)", "system": "System"}


def make_model() -> OpenAIResponsesModel:
    """The one model the app uses. Raises if no key is configured."""
    cfg = provider_config()
    if cfg is None:
        raise RuntimeError("No API key found. Set PORTKEY_API_KEY or OPENAI_API_KEY in ./.env or ../.env")
    _, base_url, key = cfg
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(base_url=base_url, api_key=key))


# ---------------------------------------------------------------- types

class AgentReply(BaseModel):
    text: str = Field(description="The reply to the learner, in plain words. Numbers only from tool results.")
    terms_used: list[str] = Field(default_factory=list, description="Glossary keys of terms used in the reply")


@dataclass
class Deps:
    session: Any  # game.Session
    agent: str
    emit: Callable[..., None]
    proposed: list[dict] = field(default_factory=list)

    @property
    def state(self):
        return self.session.state

    @property
    def revealed(self) -> set[int]:
        return set(self.session.explanations)


# ---------------------------------------------------------------- tools exposed to agents

def _done(ctx: RunContext[Deps], name: str, result: dict) -> dict:
    ctx.deps.emit(ctx.deps.agent, "tool_result", {"tool": name, "result": result})
    return result


def register_tools(agent: Agent, allowed: set[str]) -> None:
    def add(fn):
        if fn.__name__ in allowed:
            agent.tool(fn)
        return fn

    @add
    async def get_risk_dashboard(ctx: RunContext[Deps]) -> dict:
        """Headline risk numbers now: surplus, capital and liquidity ratios, rate mismatch, exposures, traffic lights."""
        return _done(ctx, "get_risk_dashboard", tools.get_risk_dashboard(ctx.deps.state))

    @add
    async def get_news_signal(ctx: RunContext[Deps]) -> dict:
        """This quarter's news-wire hint (not a forecast) and whether a pension deal is on offer."""
        return _done(ctx, "get_news_signal", tools.get_news_signal(ctx.deps.state))

    @add
    async def get_past_quarter(ctx: RunContext[Deps], quarter: int) -> dict:
        """What happened in a quarter already played. The breakdown by cause is only shown once revealed."""
        return _done(ctx, "get_past_quarter", tools.get_past_quarter(ctx.deps.state, quarter, ctx.deps.revealed))

    @add
    async def glossary_lookup(ctx: RunContext[Deps], term: str) -> dict:
        """Approved plain-English definition of a term."""
        return _done(ctx, "glossary_lookup", tools.glossary_lookup(term))

    @add
    async def get_liability_summary(ctx: RunContext[Deps]) -> dict:
        """Liabilities by type with durations, surrenderable shares, crediting rate and annuity book vs market value."""
        return _done(ctx, "get_liability_summary", tools.get_liability_summary(ctx.deps.state))

    @add
    async def get_surrender_projection(ctx: RunContext[Deps], rate_rise_bp: float = 100, lapse_multiple: float = 1.5) -> dict:
        """Extra surrender cash outflow if rates rise by rate_rise_bp and surrenders run at lapse_multiple x normal."""
        return _done(ctx, "get_surrender_projection",
                     tools.get_surrender_projection(ctx.deps.state, rate_rise_bp, lapse_multiple))

    @add
    async def get_guarantee_exposure(ctx: RunContext[Deps]) -> dict:
        """Variable annuity guarantees: size, value, cost if stocks or rates fall, and how much is hedged."""
        return _done(ctx, "get_guarantee_exposure", tools.get_guarantee_exposure(ctx.deps.state))

    @add
    async def get_asset_summary(ctx: RunContext[Deps]) -> dict:
        """Assets by type with value, duration, yield and capital charge."""
        return _done(ctx, "get_asset_summary", tools.get_asset_summary(ctx.deps.state))

    @add
    async def get_credit_exposure(ctx: RunContext[Deps]) -> dict:
        """Credit holdings by rating (AAA, A, BBB, junk), mortgages, and the loss if spreads widen 100bp."""
        return _done(ctx, "get_credit_exposure", tools.get_credit_exposure(ctx.deps.state))

    @add
    async def get_liquidity_ladder(ctx: RunContext[Deps]) -> dict:
        """What can be sold for cash, in order, with normal and stressed haircuts, and the 90-day stressed outflow."""
        return _done(ctx, "get_liquidity_ladder", tools.get_liquidity_ladder(ctx.deps.state))

    @add
    async def get_hedge_costs(ctx: RunContext[Deps]) -> dict:
        """Current hedges and what each extra 10% of hedging costs per quarter."""
        return _done(ctx, "get_hedge_costs", tools.get_hedge_costs(ctx.deps.state))

    @add
    async def stress_test(ctx: RunContext[Deps], rate_bp: float = 0, ig_spread_bp: float = 0,
                          equity_pct: float = 0, fx_pct: float = 0) -> dict:
        """Hypothetical what-if on today's book: surplus change by cause for given market moves. Not a forecast."""
        return _done(ctx, "stress_test", tools.stress_test(ctx.deps.state, rate_bp, ig_spread_bp, equity_pct, fx_pct))

    @add
    async def preview_trade(ctx: RunContext[Deps], rate_hedge_pct: float | None = None,
                            credit_shift_pct: float | None = None, equity_hedge_pct: float | None = None,
                            fx_hedge_pct: float | None = None, cash_buffer_pct: float | None = None,
                            collateralized: bool | None = None, dealers: int | None = None) -> dict:
        """Dashboard before and after a possible trade (unspecified levers keep current values), plus its cost."""
        try:
            act = tools.validate_ticket(dict(rate_hedge_pct=rate_hedge_pct, credit_shift_pct=credit_shift_pct,
                                             equity_hedge_pct=equity_hedge_pct, fx_hedge_pct=fx_hedge_pct,
                                             cash_buffer_pct=cash_buffer_pct, collateralized=collateralized,
                                             dealers=dealers), ctx.deps.state)
        except Exception as e:  # out-of-range values
            return _done(ctx, "preview_trade", {"error": f"Invalid trade: {e}"})
        return _done(ctx, "preview_trade", tools.preview_trade(ctx.deps.state, act))

    @add
    async def propose_trade(ctx: RunContext[Deps], rationale: str, rate_hedge_pct: float | None = None,
                            credit_shift_pct: float | None = None, equity_hedge_pct: float | None = None,
                            fx_hedge_pct: float | None = None, cash_buffer_pct: float | None = None,
                            collateralized: bool | None = None, dealers: int | None = None,
                            accept_prt: bool | None = None) -> dict:
        """Write a trade ticket for the learner to review and sign. Never executes. Use only when asked to set up a trade."""
        try:
            act = tools.validate_ticket(dict(rate_hedge_pct=rate_hedge_pct, credit_shift_pct=credit_shift_pct,
                                             equity_hedge_pct=equity_hedge_pct, fx_hedge_pct=fx_hedge_pct,
                                             cash_buffer_pct=cash_buffer_pct, collateralized=collateralized,
                                             dealers=dealers, accept_prt=accept_prt), ctx.deps.state)
        except Exception as e:
            return _done(ctx, "propose_trade", {"error": f"Invalid trade: {e}"})
        ticket = {"action": act.model_dump(), "rationale": rationale[:400], "by": ctx.deps.agent}
        ctx.deps.proposed.append(ticket)
        return _done(ctx, "propose_trade", {"status": "Ticket written. The learner must review and sign it; nothing was executed.",
                                            "ticket": act.model_dump()})


SOLO_TOOLS = {"get_risk_dashboard", "get_news_signal", "get_past_quarter", "glossary_lookup",
              "get_liability_summary", "get_surrender_projection", "get_guarantee_exposure",
              "get_asset_summary", "get_credit_exposure", "get_liquidity_ladder", "get_hedge_costs",
              "stress_test", "preview_trade", "propose_trade"}


def load_prompt(name: str) -> str:
    """Prompt text with the glossary inserted. Stable text first so the provider can cache it."""
    return (PROMPTS / name).read_text(encoding="utf-8").replace("{GLOSSARY}", tools.glossary_text())


@lru_cache(maxsize=None)
def get_agent(kind: str) -> Agent:
    if kind != "solo":
        raise ValueError(kind)
    agent = Agent(make_model(), deps_type=Deps, output_type=AgentReply, instructions=load_prompt("solo.md"),
                  retries=1, name="solo")
    register_tools(agent, SOLO_TOOLS)
    return agent


# ---------------------------------------------------------------- usage and budget

def _record_usage(session, agent: str, run_id: str, resp) -> dict:
    u = resp.usage
    reasoning = int((u.details or {}).get("reasoning_tokens", 0))
    cost = cost_usd(u.input_tokens, u.output_tokens, u.cache_read_tokens, u.cache_write_tokens)
    t = session.tokens
    t["input"] += u.input_tokens
    t["cached"] += u.cache_read_tokens
    t["cache_write"] += u.cache_write_tokens
    t["output"] += u.output_tokens
    t["reasoning"] += reasoning
    t["requests"] += 1
    session.spend_usd += cost
    a = session.by_agent.setdefault(agent, {"input": 0, "cached": 0, "output": 0, "requests": 0, "cost_usd": 0.0})
    a["input"] += u.input_tokens
    a["cached"] += u.cache_read_tokens
    a["output"] += u.output_tokens
    a["requests"] += 1
    a["cost_usd"] = round(a["cost_usd"] + cost, 6)
    rec = {"session_id": session.id, "run_id": run_id, "agent": agent, "model": MODEL_NAME,
           "input_tokens": u.input_tokens, "cache_read_tokens": u.cache_read_tokens,
           "cache_write_tokens": u.cache_write_tokens, "output_tokens": u.output_tokens,
           "reasoning_tokens": reasoning, "cost_usd": round(cost, 6)}
    audit.usage(rec)
    return rec


OFFLINE_TEXT = ("My colleagues and I are offline for this session, so I can't answer questions right now. "
                "The game still works: every number on the dashboard comes from the engine, "
                "and the trade ticket preview shows the effect of each lever.")
BUDGET_TEXT = ("We've hit this session's AI budget cap, so the colleagues are offline. "
               "The game continues: use the dashboard and the ticket preview, or raise the cap in Under the hood.")


# ---------------------------------------------------------------- the run

_HISTORY: dict[str, list[list[ModelMessage]]] = {}


async def ask(session, message: str, queue: asyncio.Queue, save: Callable[[Any], None]) -> None:
    """Answer one learner question. Puts events on `queue` (and the audit trail); None marks the end."""
    run_id = secrets.token_hex(4)
    quarter = min(session.state.quarter, 4)
    agent_key = "solo"

    def emit(agent: str, type_: str, detail, **tok) -> dict:
        ev = audit.event(session.id, run_id, quarter, agent, type_, detail, **tok)
        ev["agent_name"] = AGENT_NAMES.get(agent, agent)
        queue.put_nowait(ev)
        return ev

    t0 = time.time()
    session.chat.append({"role": "user", "text": message, "run_id": run_id, "ts": t0})
    reply_text, terms, stopped, proposed = None, [], None, []

    try:
        if not load_env().key_found:
            stopped = "no_key"
            emit("system", "blocked", {"reason": "no_key", "message": OFFLINE_TEXT})
        elif session.spend_usd >= session.budget_cap_usd:
            stopped = "budget"
            emit("system", "blocked", {"reason": "budget", "message": BUDGET_TEXT,
                                       "spend_usd": round(session.spend_usd, 6), "cap_usd": session.budget_cap_usd})
        else:
            agent = get_agent(agent_key)
            deps = Deps(session=session, agent=agent_key, emit=emit)
            history = [m for run in _HISTORY.get(session.id, [])[-HISTORY_RUNS:] for m in run]
            company = DISPLAY_NAMES.get(session.ticker, session.ticker)
            prompt = f"[Quarter {quarter} of 4 | {company} ({session.ticker}) | phase: {session.phase}]\nLearner: {message}"
            emit(agent_key, "start", {"question": message})
            result = None
            async with agent.iter(prompt, deps=deps, message_history=history,
                                  usage_limits=UsageLimits(request_limit=REQUEST_LIMIT)) as run:
                async for node in run:
                    if Agent.is_call_tools_node(node):
                        resp = node.model_response
                        rec = _record_usage(session, agent_key, run_id, resp)
                        emit(agent_key, "spend", {"model": MODEL_NAME, "reasoning_tokens": rec["reasoning_tokens"],
                                                  "session_spend_usd": round(session.spend_usd, 6),
                                                  "cap_usd": session.budget_cap_usd},
                             input_tokens=rec["input_tokens"], cached_tokens=rec["cache_read_tokens"],
                             output_tokens=rec["output_tokens"], cost_usd=rec["cost_usd"])
                        calls = [p for p in resp.parts if isinstance(p, ToolCallPart)]
                        final = any(p.tool_name == "final_result" for p in calls)
                        for p in calls:
                            if p.tool_name != "final_result":
                                emit(agent_key, "tool_call", {"tool": p.tool_name, "args": p.args_as_dict()})
                        if not final and session.spend_usd >= session.budget_cap_usd:
                            stopped = "budget"
                            emit("system", "blocked", {"reason": "budget", "message": BUDGET_TEXT,
                                                       "spend_usd": round(session.spend_usd, 6),
                                                       "cap_usd": session.budget_cap_usd})
                            break
                result = run.result
            if result is not None:
                reply_text, terms = result.output.text, result.output.terms_used
                _HISTORY.setdefault(session.id, []).append(result.new_messages())
            proposed = deps.proposed
    except UsageLimitExceeded:
        stopped = "request_limit"
        emit("system", "stop", {"reason": "request_limit",
                                "message": f"Stopped after {REQUEST_LIMIT} model requests (loop guard)."})
    except Exception as e:  # provider or validation failure: plain fallback, never the key
        stopped = "error"
        emit("system", "error", {"message": redact(f"{type(e).__name__}: {e}")[:300]})

    if reply_text is None:
        reply_text = {"no_key": OFFLINE_TEXT, "budget": BUDGET_TEXT}.get(
            stopped or "", "Sorry, I couldn't finish that answer. Please try again or rephrase.")
    if proposed:
        session.proposed_ticket = proposed[-1]
    emit(agent_key if stopped is None else "system", "reply",
         {"text": reply_text, "terms_used": terms, "proposed_ticket": proposed[-1] if proposed else None,
          "stopped": stopped, "seconds": round(time.time() - t0, 2)})
    session.chat.append({"role": "agent", "agent": agent_key if stopped is None else "system",
                         "agent_name": AGENT_NAMES.get(agent_key if stopped is None else "system"),
                         "text": reply_text, "run_id": run_id, "stopped": stopped,
                         "proposed_ticket": proposed[-1] if proposed else None, "ts": time.time()})
    emit("system", "usage", {"spend_usd": round(session.spend_usd, 6), "budget_cap_usd": session.budget_cap_usd,
                             "blocked": session.spend_usd >= session.budget_cap_usd, "tokens": session.tokens,
                             "by_agent": session.by_agent})
    save(session)
