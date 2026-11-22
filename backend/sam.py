"""Sam Nakamura, Calibration Analyst: reads targeted 10-K chunks for figures that are not tagged.

Sam has read-only tools over one filing and a typed output. Code validates every finding:
the chunk must be one Sam retrieved, the quote must appear in that chunk, the number must
appear in the quote, and the resulting share must sit inside a sanity range. Anything else
is rejected, logged, and replaced by the labelled default.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ToolCallPart

from backend import agents, audit, filings
from backend.calibration import get_tagged_facts as tagged_facts, load_assumptions

FIELDS = ("govt_bonds", "below_ig_bonds", "bbb_bonds", "rate_sensitivity_100bp", "guaranteed_account_value", "foreign_share")


class Finding(BaseModel):
    field: Literal["govt_bonds", "below_ig_bonds", "bbb_bonds", "rate_sensitivity_100bp",
                   "guaranteed_account_value", "foreign_share"]
    value: float = Field(description="The number exactly as in the quote (in millions for usd_mn)")
    unit: Literal["pct", "usd_mn"]
    chunk_id: int
    quote: str = Field(description="Exact words copied from the chunk, including the number")
    note: str = ""


class SamFindings(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    not_found: list[str] = Field(default_factory=list)


@dataclass
class CalibRun:
    """Stands in for a game session in usage accounting."""
    id: str
    ticker: str
    spend_usd: float = 0.0
    budget_cap_usd: float = 0.10
    tokens: dict = field(default_factory=lambda: {"input": 0, "cached": 0, "cache_write": 0, "output": 0, "reasoning": 0, "requests": 0})
    by_agent: dict = field(default_factory=dict)
    retrieved: dict[int, str] = field(default_factory=dict)
    tagged_override: dict | None = None  # Safety Lab fixtures (fictional companies have no EDGAR data)
    searches: int = 0
    events: list[dict] = field(default_factory=list)


@lru_cache(maxsize=1)
def _agent() -> Agent:
    agent = Agent(agents.make_model(), deps_type=CalibRun, output_type=SamFindings,
                  instructions=(agents.PROMPTS / "calibration.md").read_text(encoding="utf-8"), retries=1, name="calibration")

    @agent.tool
    async def search_filing(ctx: RunContext[CalibRun], query: str, k: int = 4) -> dict:
        """Keyword search over the sanitized 10-K. Returns the top-k chunks (about 1,400 characters each)."""
        run = ctx.deps
        run.searches += 1
        if run.searches > 16:
            return {"error": "Search limit reached (16). Report what you have."}
        hits = filings.search(run.ticker, query, min(max(k, 1), 6))
        for h in hits:
            run.retrieved[h["chunk_id"]] = h["text"]
        return {"query": query, "chunks": [{"chunk_id": h["chunk_id"], "text": h["text"]} for h in hits]}

    @agent.tool
    async def read_next_chunks(ctx: RunContext[CalibRun], chunk_id: int, count: int = 2) -> dict:
        """Read the chunks that follow a chunk you already have (tables often continue into the next chunk)."""
        run = ctx.deps
        run.searches += 1
        if run.searches > 16:
            return {"error": "Reading limit reached (16 searches and reads). Report what you have now."}
        all_chunks = {c["chunk_id"]: c["text"] for c in filings.chunks_for(run.ticker)[0]}
        if chunk_id not in run.retrieved:
            return {"error": "You can only continue from a chunk you have already retrieved."}
        out = []
        for i in range(chunk_id + 1, chunk_id + 1 + min(max(count, 1), 3)):
            if i in all_chunks:
                run.retrieved[i] = all_chunks[i]
                out.append({"chunk_id": i, "text": all_chunks[i]})
        return {"chunks": out}

    @agent.tool
    async def get_tagged_facts(ctx: RunContext[CalibRun]) -> dict:
        """Tagged XBRL facts already known for this company ($ billions), for scale."""
        if ctx.deps.tagged_override is not None:
            return ctx.deps.tagged_override
        f = tagged_facts(ctx.deps.ticker)
        keep = ("investments", "bonds_afs", "bonds_trading", "separate_account_assets", "policyholder_account_balances",
                "future_policy_benefits")
        return {k: f[k].value for k in keep}

    @agent.tool
    async def get_default_assumption(ctx: RunContext[CalibRun], name: str) -> dict:
        """The labelled default used if a figure cannot be found."""
        d = load_assumptions()["defaults_when_untagged"]
        return {"name": name, "default": d.get(name), "all": d}

    return agent


async def run_sam(ticker: str, cap_usd: float = 0.10, tagged_override: dict | None = None) -> tuple[SamFindings | None, CalibRun]:
    run = CalibRun(id=f"calibration-{ticker}-{secrets.token_hex(3)}", ticker=ticker, budget_cap_usd=cap_usd,
                   tagged_override=tagged_override)
    if not agents.ai_available():
        return None, run
    filings.chunks_for(ticker)  # warm the index
    try:
        return await _iterate(ticker, run), run
    except UsageLimitExceeded:
        run.events.append({"type": "stop", "detail": "request limit reached; labelled defaults used"})
        return None, run


async def _iterate(ticker: str, run: CalibRun) -> SamFindings | None:
    result = None
    async with _agent().iter(f"Company: {ticker}. Find the figures listed in your instructions.", deps=run,
                             usage_limits=UsageLimits(request_limit=20)) as it:
        async for node in it:
            if Agent.is_call_tools_node(node):
                rec = agents._record_usage(run, "calibration", run.id, node.model_response)
                for p in node.model_response.parts:
                    if isinstance(p, ToolCallPart) and p.tool_name != "final_result":
                        ev = audit.event(run.id, run.id, 0, "calibration", "tool_call", {"tool": p.tool_name, "args": p.args_as_dict()},
                                         input_tokens=rec["input_tokens"], cached_tokens=rec["cache_read_tokens"],
                                         output_tokens=rec["output_tokens"], cost_usd=rec["cost_usd"])
                        run.events.append(ev)
                if run.spend_usd >= run.budget_cap_usd:
                    break
        result = it.result
    return result.output if result else None


# ---------------------------------------------------------------- validation in code

def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("—", "-").replace("–", "-")
    s = re.sub(r"\s*\|\s*", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def _digits(s: str) -> str:
    return re.sub(r"[^\d.]", "", s)


def _number_in_quote(value: float, quote: str) -> bool:
    q = quote.replace(",", "")
    nums = re.findall(r"\d+(?:\.\d+)?", q)
    target = abs(value)
    for n in nums:
        x = float(n)
        if abs(x - target) <= max(0.005 * target, 0.051):
            return True
        if abs(x * 1000 - target) <= 0.005 * target:  # table in billions, value in millions
            return True
    return False


RANGES = {
    "govt_share_of_bonds": (0.0, 0.5),
    "below_ig_share_of_bonds": (0.0, 0.25),
    "bbb_share_of_bonds": (0.05, 0.65),
    "foreign_share": (0.0, 0.7),
}


def validate(findings: SamFindings | None, run: CalibRun, tagged: dict) -> tuple[dict, list[dict]]:
    """Returns (accepted values keyed by profile field with citation, rejections)."""
    accepted, rejected = {}, []
    if findings is None:
        return accepted, [{"field": "*", "reason": "AI unavailable: tagged facts and labelled defaults only"}]
    bonds_mn = 1000 * ((tagged["bonds_afs"].value or 0) + (tagged["bonds_trading"].value or 0))
    sa_mn = 1000 * (tagged["separate_account_assets"].value or 0)
    invested_mn = 1000 * (tagged["investments"].value or 0)

    for f in findings.findings:
        def reject(reason: str):
            rejected.append({"field": f.field, "value": f.value, "unit": f.unit, "chunk_id": f.chunk_id,
                             "quote": f.quote[:200], "reason": reason})

        chunk = run.retrieved.get(f.chunk_id)
        if chunk is None:
            reject("chunk was not one Sam retrieved")
            continue
        if _norm(f.quote) not in _norm(chunk) or len(f.quote.split()) < 3:
            reject("quote not found word-for-word in the chunk")
            continue
        if not _number_in_quote(f.value, f.quote):
            reject("the number is not in the quote")
            continue
        cite = f"10-K text, chunk {f.chunk_id}: \"{f.quote.strip()[:180]}\""

        def share(v: float) -> float | None:
            return v / 100 if f.unit == "pct" else (v / bonds_mn if bonds_mn else None)

        if f.field in ("govt_bonds", "below_ig_bonds", "bbb_bonds"):
            name = {"govt_bonds": "govt_share_of_bonds", "below_ig_bonds": "below_ig_share_of_bonds",
                    "bbb_bonds": "bbb_share_of_bonds"}[f.field]
            v = share(f.value)
            lo, hi = RANGES[name]
            if v is None or not lo <= v <= hi:
                reject(f"share {v} outside sanity range {lo}-{hi}")
                continue
            if name in accepted and f.unit == "usd_mn" and accepted[name]["unit"] == "usd_mn":
                accepted[name]["value"] += v  # e.g. U.S. government + foreign governments rows
                accepted[name]["citation"] += " + " + cite
                continue
            accepted[name] = {"value": v, "unit": f.unit, "citation": cite, "note": f.note}
        elif f.field == "foreign_share":
            v = f.value / 100 if f.unit == "pct" else None
            lo, hi = RANGES["foreign_share"]
            if v is None or not lo <= v <= hi:
                reject(f"foreign share {v} outside sanity range {lo}-{hi}")
                continue
            accepted["foreign_share"] = {"value": v, "unit": "pct", "citation": cite, "note": f.note}
        elif f.field == "rate_sensitivity_100bp":
            if f.unit != "usd_mn" or abs(f.value) > 0.5 * invested_mn or f.value == 0:
                reject("rate sensitivity must be a non-zero $ amount below half of invested assets")
                continue
            if not re.search(r"\b(total|net|surplus|equity|shareholders|stockholders)\b", f.quote, re.I):
                reject("rate sensitivity quote is not a total or net line")
                continue
            accepted["rate_sensitivity"] = {"value": f.value / 1000, "unit": "usd_bn", "citation": cite, "note": f.note}
        elif f.field == "guaranteed_account_value":
            if f.unit != "usd_mn" or not 0 < f.value <= 1.2 * sa_mn:
                reject("guaranteed account value must be positive and at most 1.2x separate-account assets")
                continue
            accepted["guaranteed_account_value"] = {"value": f.value / 1000, "unit": "usd_bn", "citation": cite, "note": f.note}

    # the three bond shares must leave room for investment-grade corporates
    total = sum(accepted.get(k, {}).get("value", 0) for k in ("govt_share_of_bonds", "below_ig_share_of_bonds", "bbb_share_of_bonds"))
    if total > 0.95:
        for k in ("bbb_share_of_bonds",):
            if k in accepted:
                rejected.append({"field": k, "value": accepted[k]["value"], "reason": "bond shares sum above 95%"})
                accepted.pop(k)
    return accepted, rejected
