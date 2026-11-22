"""Agents. Every model call goes to gpt-6-luna, through Portkey or OpenAI.

Solo mode: one agent (Amara's voice) holding every read tool plus propose_trade.
Team mode: Amara (CRO) routes the learner's question to specialists through async
delegation tools; each specialist holds only its own tools (permissions, plan 6.2).
Every model call is logged with API-reported usage, and a hard budget cap is checked
before a run and after every model response, in every agent.
"""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
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
MAX_DELEGATIONS = 3
HISTORY_RUNS = 3  # short-term memory: the last few question/answer exchanges

AGENT_NAMES = {
    "solo": "Dr. Amara Okafor (Solo)",
    "cro": "Dr. Amara Okafor (CRO)",
    "actuary": "Walt Brennan (Actuary)",
    "portfolio_manager": "Priya Raman (Portfolio Manager)",
    "trader": "Teo Vargas (Trader)",
    "system": "System",
}
WORKERS = ("actuary", "portfolio_manager", "trader")


def ai_available() -> bool:
    """True when a key is configured and AI is not switched off (tests set RISK_DESK_OFFLINE=1)."""
    return load_env().key_found and not os.environ.get("RISK_DESK_OFFLINE")


def make_model() -> OpenAIResponsesModel:
    """The one model the app uses. Raises if no key is configured."""
    cfg = provider_config()
    if cfg is None:
        raise RuntimeError("No API key found. Set PORTKEY_API_KEY or OPENAI_API_KEY in ./.env or ../.env")
    _, base_url, key = cfg
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(base_url=base_url, api_key=key))


# ---------------------------------------------------------------- types

class AgentReply(BaseModel):
    text: str = Field(description="The reply, in plain words. Numbers only from tool results.")
    terms_used: list[str] = Field(default_factory=list, description="Glossary keys of terms used in the reply")


@dataclass
class RunCtx:
    """Shared by every agent taking part in answering one learner question."""
    session: Any  # game.Session
    run_id: str
    emit: Callable[..., dict]
    proposed: list[dict] = field(default_factory=list)
    subs: list[dict] = field(default_factory=list)  # specialists' answers, shown to the learner
    delegations: int = 0
    stopped: str | None = None


@dataclass
class Deps:
    run: RunCtx
    agent: str

    @property
    def state(self):
        return self.run.session.state

    @property
    def revealed(self) -> set[int]:
        return set(self.run.session.explanations)


# ---------------------------------------------------------------- tools exposed to agents

def _done(ctx: RunContext[Deps], name: str, result: dict) -> dict:
    ctx.deps.run.emit(ctx.deps.agent, "tool_result", {"tool": name, "result": result})
    return result


def _ticket(ctx: RunContext[Deps], **levers) -> tuple[Any, str | None]:
    try:
        return tools.validate_ticket(levers, ctx.deps.state), None
    except Exception as e:  # out-of-range values come back to the model as an error
        return None, f"Invalid trade: {e}"


async def _delegate(ctx: RunContext[Deps], worker: str, task: str) -> dict:
    run = ctx.deps.run
    if run.delegations >= MAX_DELEGATIONS:
        return {"error": f"Delegation limit reached ({MAX_DELEGATIONS} per question). Answer with what you have."}
    if run.stopped:
        return {"error": "The session budget cap was reached; the specialist is offline."}
    run.delegations += 1
    run.emit(ctx.deps.agent, "delegation", {"to": worker, "to_name": AGENT_NAMES[worker], "task": task[:600]})
    out = await _run_agent(worker, f"Question from Dr. Amara Okafor (CRO): {task}", run)
    if out is None:
        return {"error": f"{AGENT_NAMES[worker]} could not answer ({run.stopped or 'error'})."}
    run.emit(worker, "delegation", {"from": worker, "from_name": AGENT_NAMES[worker], "answer": out.text,
                                    "terms_used": out.terms_used})
    run.subs.append({"agent": worker, "agent_name": AGENT_NAMES[worker], "text": out.text})
    return {"from": AGENT_NAMES[worker], "answer": out.text}


def register_tools(agent: Agent, allowed: set[str]) -> None:
    def add(fn):
        if fn.__name__ in allowed:
            agent.tool(fn)
        return fn

    # --- delegation (CRO only)
    @add
    async def ask_actuary(ctx: RunContext[Deps], task: str) -> dict:
        """Ask Walt Brennan, the Actuary: liabilities, surrenders, stock-market guarantees. Give a focused task."""
        return await _delegate(ctx, "actuary", task)

    @add
    async def ask_portfolio_manager(ctx: RunContext[Deps], task: str) -> dict:
        """Ask Priya Raman, the Portfolio Manager: investments, credit quality, liquidity. Give a focused task."""
        return await _delegate(ctx, "portfolio_manager", task)

    @add
    async def ask_trader(ctx: RunContext[Deps], task: str) -> dict:
        """Ask Teo Vargas, the Trader: hedges, hedge costs, trade previews and tickets. Give a focused task."""
        return await _delegate(ctx, "trader", task)

    # --- shared reads
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

    # --- liabilities (Actuary)
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

    # --- assets (Portfolio Manager)
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

    # --- hedges (Trader)
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
        act, err = _ticket(ctx, rate_hedge_pct=rate_hedge_pct, credit_shift_pct=credit_shift_pct,
                           equity_hedge_pct=equity_hedge_pct, fx_hedge_pct=fx_hedge_pct,
                           cash_buffer_pct=cash_buffer_pct, collateralized=collateralized, dealers=dealers)
        return _done(ctx, "preview_trade", {"error": err} if err else tools.preview_trade(ctx.deps.state, act))

    @add
    async def propose_trade(ctx: RunContext[Deps], rationale: str, rate_hedge_pct: float | None = None,
                            credit_shift_pct: float | None = None, equity_hedge_pct: float | None = None,
                            fx_hedge_pct: float | None = None, cash_buffer_pct: float | None = None,
                            collateralized: bool | None = None, dealers: int | None = None,
                            accept_prt: bool | None = None) -> dict:
        """Write a trade ticket for the learner to review and sign. Never executes. Use only when asked to set up a trade."""
        act, err = _ticket(ctx, rate_hedge_pct=rate_hedge_pct, credit_shift_pct=credit_shift_pct,
                           equity_hedge_pct=equity_hedge_pct, fx_hedge_pct=fx_hedge_pct,
                           cash_buffer_pct=cash_buffer_pct, collateralized=collateralized, dealers=dealers,
                           accept_prt=accept_prt)
        if err:
            return _done(ctx, "propose_trade", {"error": err})
        ctx.deps.run.proposed.append({"action": act.model_dump(), "rationale": rationale[:400],
                                      "by": AGENT_NAMES[ctx.deps.agent]})
        return _done(ctx, "propose_trade", {"status": "Ticket written. The learner must review and sign it; nothing was executed.",
                                            "ticket": act.model_dump()})


# ---------------------------------------------------------------- the cast and its permissions (plan 6.2)

SHARED = {"glossary_lookup"}
TOOLSETS: dict[str, set[str]] = {
    "solo": {"get_risk_dashboard", "get_news_signal", "get_past_quarter", "get_liability_summary",
             "get_surrender_projection", "get_guarantee_exposure", "get_asset_summary", "get_credit_exposure",
             "get_liquidity_ladder", "get_hedge_costs", "stress_test", "preview_trade", "propose_trade"} | SHARED,
    "cro": {"ask_actuary", "ask_portfolio_manager", "ask_trader", "get_risk_dashboard", "get_news_signal",
            "get_past_quarter"} | SHARED,
    "actuary": {"get_liability_summary", "get_surrender_projection", "get_guarantee_exposure"} | SHARED,
    "portfolio_manager": {"get_asset_summary", "get_credit_exposure", "get_liquidity_ladder"} | SHARED,
    "trader": {"get_hedge_costs", "stress_test", "preview_trade", "propose_trade"} | SHARED,
}
SOLO_TOOLS = TOOLSETS["solo"]  # kept for tests and the harness description
PROMPT_FILES = {"solo": "solo.md", "cro": "cro.md", "actuary": "actuary.md",
                "portfolio_manager": "portfolio_manager.md", "trader": "trader.md"}


def load_prompt(name: str) -> str:
    """Prompt text with shared rules and the glossary inserted. All stable text, so the provider can cache it."""
    rules = (PROMPTS / "_rules.md").read_text(encoding="utf-8")
    text = (PROMPTS / name).read_text(encoding="utf-8").replace("{RULES}", rules)
    return text.replace("{GLOSSARY}", tools.glossary_text())


@lru_cache(maxsize=None)
def get_agent(kind: str) -> Agent:
    agent = Agent(make_model(), deps_type=Deps, output_type=AgentReply, instructions=load_prompt(PROMPT_FILES[kind]),
                  retries=1, name=kind)
    register_tools(agent, TOOLSETS[kind])
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


def _block_budget(run: RunCtx) -> None:
    if run.stopped != "budget":
        run.stopped = "budget"
        s = run.session
        run.emit("system", "blocked", {"reason": "budget", "message": BUDGET_TEXT,
                                       "spend_usd": round(s.spend_usd, 6), "cap_usd": s.budget_cap_usd})


async def _run_agent(kind: str, prompt: str, run: RunCtx, history: list[ModelMessage] | None = None):
    """One agent run with per-response usage logging and the budget check. Returns the run result or None."""
    s = run.session
    if s.spend_usd >= s.budget_cap_usd:
        _block_budget(run)
        return None
    agent = get_agent(kind)
    deps = Deps(run=run, agent=kind)
    run.emit(kind, "start", {"prompt": prompt[:600]})
    async with agent.iter(prompt, deps=deps, message_history=history or [],
                          usage_limits=UsageLimits(request_limit=REQUEST_LIMIT)) as it:
        async for node in it:
            if Agent.is_call_tools_node(node):
                resp = node.model_response
                rec = _record_usage(s, kind, run.run_id, resp)
                run.emit(kind, "spend", {"model": MODEL_NAME, "reasoning_tokens": rec["reasoning_tokens"],
                                         "session_spend_usd": round(s.spend_usd, 6), "cap_usd": s.budget_cap_usd},
                         input_tokens=rec["input_tokens"], cached_tokens=rec["cache_read_tokens"],
                         output_tokens=rec["output_tokens"], cost_usd=rec["cost_usd"])
                calls = [p for p in resp.parts if isinstance(p, ToolCallPart)]
                final = any(p.tool_name == "final_result" for p in calls)
                for p in calls:
                    if p.tool_name != "final_result":
                        run.emit(kind, "tool_call", {"tool": p.tool_name, "args": p.args_as_dict()})
                if not final and s.spend_usd >= s.budget_cap_usd:
                    _block_budget(run)
                    return None
        result = it.result
    if result is not None:
        return result if history is not None else result.output
    return None


# ---------------------------------------------------------------- one learner question

_HISTORY: dict[str, list[list[ModelMessage]]] = {}


async def ask(session, message: str, queue: asyncio.Queue, save: Callable[[Any], None], to: str | None = None) -> None:
    """Answer one learner question. Puts events on `queue` (and the audit trail)."""
    run_id = secrets.token_hex(4)
    quarter = min(session.state.quarter, 4)
    if session.agent_mode == "solo":
        lead = "solo"
    elif to in WORKERS:
        lead = to  # the learner addressed one colleague directly
    else:
        lead = "cro"

    def emit(agent: str, type_: str, detail, **tok) -> dict:
        ev = audit.event(session.id, run_id, quarter, agent, type_, detail, **tok)
        ev["agent_name"] = AGENT_NAMES.get(agent, agent)
        queue.put_nowait(ev)
        return ev

    run = RunCtx(session=session, run_id=run_id, emit=emit)
    t0 = time.time()
    session.chat.append({"role": "user", "text": message, "run_id": run_id, "ts": t0, "to": lead})
    reply_text, terms = None, []

    try:
        if not ai_available():
            run.stopped = "no_key"
            emit("system", "blocked", {"reason": "no_key", "message": OFFLINE_TEXT})
        else:
            company = DISPLAY_NAMES.get(session.ticker, session.ticker)
            prompt = f"[Quarter {quarter} of 4 | {company} ({session.ticker}) | phase: {session.phase}]\nLearner: {message}"
            history = [m for r in _HISTORY.get(f"{session.id}:{lead}", [])[-HISTORY_RUNS:] for m in r]
            result = await _run_agent(lead, prompt, run, history=history)
            if result is not None:
                reply_text, terms = result.output.text, result.output.terms_used
                _HISTORY.setdefault(f"{session.id}:{lead}", []).append(result.new_messages())
    except UsageLimitExceeded:
        run.stopped = "request_limit"
        emit("system", "stop", {"reason": "request_limit",
                                "message": f"Stopped after {REQUEST_LIMIT} model requests in one agent (loop guard)."})
    except Exception as e:  # provider or validation failure: plain fallback, never the key
        run.stopped = run.stopped or "error"
        emit("system", "error", {"message": redact(f"{type(e).__name__}: {e}")[:300]})

    stopped = run.stopped if reply_text is None else None
    if reply_text is None:
        reply_text = {"no_key": OFFLINE_TEXT, "budget": BUDGET_TEXT}.get(
            stopped or "", "Sorry, I couldn't finish that answer. Please try again or rephrase.")
    speaker = lead if stopped is None else "system"
    ticket = run.proposed[-1] if run.proposed else None
    if ticket:
        session.proposed_ticket = ticket
    emit(speaker, "reply", {"text": reply_text, "terms_used": terms, "proposed_ticket": ticket,
                            "stopped": stopped, "delegations": run.delegations, "subs": run.subs,
                            "seconds": round(time.time() - t0, 2)})
    session.chat.append({"role": "agent", "agent": speaker, "agent_name": AGENT_NAMES.get(speaker),
                         "text": reply_text, "run_id": run_id, "stopped": stopped, "subs": run.subs,
                         "proposed_ticket": ticket, "ts": time.time()})
    emit("system", "usage", {"spend_usd": round(session.spend_usd, 6), "budget_cap_usd": session.budget_cap_usd,
                             "blocked": session.spend_usd >= session.budget_cap_usd, "tokens": session.tokens,
                             "by_agent": session.by_agent})
    save(session)
