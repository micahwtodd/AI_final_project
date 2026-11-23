"""Shared Pydantic types. Every number in the game lives in one of these."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ASSET_BUCKETS = ["govt", "ig_corp", "below_ig", "mortgage", "alts", "cash"]  # stocks are folded into alts
LIABILITY_BUCKETS = ["annuities", "life", "prt", "other"]  # VA guarantees are tracked separately

ASSET_LABELS = {
    "govt": "Government and agency bonds",
    "ig_corp": "Investment-grade corporates",
    "below_ig": "Below-investment-grade",
    "mortgage": "Mortgage loans",
    "alts": "Alternatives (incl. stocks)",
    "cash": "Cash and short-term",
}
LIABILITY_LABELS = {
    "annuities": "Fixed and indexed annuities",
    "life": "Life insurance",
    "prt": "Pension risk transfer and payout annuities",
    "other": "Other",
    "guarantee": "Variable annuity guarantees",
}


# ---------- company profile ----------

class FieldSource(BaseModel):
    value: float | None
    source: Literal["tagged", "filing_text", "assumption", "derived"]
    citation: str = ""
    note: str = ""


class CompanyProfile(BaseModel):
    ticker: str
    name: str
    fiscal_year: int
    accession: str
    invested_assets_usd_bn: float = Field(description="General-account invested assets plus cash")
    surplus_usd_bn: float = Field(description="Equity excluding AOCI, used as the game's starting surplus")
    asset_mix: dict[str, float] = Field(description="Share of invested assets per asset bucket, sums to 1")
    liability_mix: dict[str, float] = Field(description="Share of modeled liabilities per bucket, sums to 1")
    guarantee_exposure_usd_bn: float = Field(description="Account value carrying VA guarantees")
    guarantee_value_usd_bn: float = Field(description="Net market risk benefit liability (can be negative)")
    separate_account_assets_usd_bn: float
    alts_beta: float = Field(0.2, description="Stock-market sensitivity of alternatives, blended with any stocks held")
    equity_to_assets: float
    net_investment_yield: float
    rate_sensitivity: float | None = Field(None, description="Disclosed surplus change for +100bp, $bn")
    foreign_share: float
    fx_exposed_share: float | None = Field(None, description="Share of invested assets exposed to currency moves "
                                                             "(foreign assets not matched by same-currency liabilities)")
    ig_bbb_share: float | None = Field(None, description="Share of investment-grade corporates rated BBB")
    ig_aaa_share: float | None = Field(None, description="Share of investment-grade corporates rated AAA")
    fields: dict[str, FieldSource] = {}
    reference: dict[str, FieldSource] = Field(default_factory=dict, description="Disclosed for reference; not used by the engine")
    rejections: list[dict] = Field(default_factory=list)
    sanitizer: dict = Field(default_factory=dict)


# ---------- market shocks and event cards ----------

class ShockVector(BaseModel):
    rate_bp: float = 0
    ig_spread_bp: float = 0
    hy_spread_bp: float = 0
    ig_loss_pct: float = 0
    hy_default_pct: float = 0
    mortgage_loss_pct: float = 0
    equity_pct: float = 0
    fx_pct: float = 0  # USD up = positive; foreign assets lose value
    lapse_mult: float = 1.0
    dealer_default: bool = False
    stress_liquidity: bool = False


class EventCard(BaseModel):
    id: str
    quarter: int
    title: str
    era: str
    signal_text: str
    headline: str
    narrative: str
    primary_risk: str
    secondary_risks: list[str]
    base_shock: ShockVector
    lesson: str
    benchmark_action: "Action"
    glossary_terms: list[str]
    source_note: str
    offers_prt_deal: bool = False
    sample_answer: str = ""
    real_world: dict = {}  # {"title", "text"}: the real episode this quarter echoes
    boss: bool = False  # the boss round: its strength is calibrated so doing nothing all game collapses the company


# ---------- the learner's levers ----------

class Action(BaseModel):
    """Absolute lever settings. Applying an Action trades the book to match it."""
    rate_hedge_pct: float = Field(0, ge=0, le=120, description="% of the duration gap closed with swaps")
    credit_shift_pct: float = Field(0, ge=-10, le=50, description="% of below-IG and BBB moved into governments")
    equity_hedge_pct: float = Field(0, ge=0, le=100, description="% of variable annuity guarantee equity exposure hedged with puts")
    fx_hedge_pct: float = Field(0, ge=0, le=100, description="% of foreign assets hedged with forwards")
    cash_buffer_pct: float = Field(3, ge=1, le=15, description="Cash as % of invested assets")
    collateralized: bool = Field(True, description="Daily collateral on derivatives")
    dealers: Literal[1, 3] = 1
    accept_prt: bool | None = Field(None, description="Pension deal decision, only when offered")


EventCard.model_rebuild()


# ---------- game state ----------

class Attribution(BaseModel):
    rates: float = 0
    credit_spreads: float = 0
    defaults: float = 0
    equity: float = 0
    fx: float = 0
    liquidity: float = 0
    counterparty: float = 0
    carry: float = 0
    hedge_cost: float = 0
    total: float = 0

    def components(self) -> dict[str, float]:
        return {k: v for k, v in self.model_dump().items() if k != "total"}


class Dashboard(BaseModel):
    surplus_usd_bn: float
    assets_usd_bn: float
    liabilities_usd_bn: float
    asset_duration_years: float
    liability_duration_years: float
    duration_gap_years: float
    net_dv01_usd_mn: float = Field(description="Surplus change for rates down 1bp, $ millions")
    liquidity_ratio_pct: float
    capital_ratio_pct: float
    net_equity_exposure_usd_bn: float
    fx_exposure_usd_bn: float
    counterparty_exposure_usd_bn: float
    derivatives_mtm_usd_bn: float = 0.0  # uncollateralized hedge value: + owed to us, - owed by us
    asset_values: dict[str, float]
    liability_values: dict[str, float]
    status: dict[str, Literal["green", "amber", "red"]]


class QuarterRecord(BaseModel):
    quarter: int
    card_id: str
    severity: float
    shock: ShockVector
    action: Action
    surplus_before: float
    surplus_after: float
    attribution: Attribution
    nothing_surplus_after: float | None = None
    benchmark_surplus_after: float | None = None
    capital_breach: bool = False
    liquidity_breach: bool = False
    benchmark_capital_breach: bool = False  # would the benchmark trades also have breached? (no penalty then)
    benchmark_liquidity_breach: bool = False
    lever_gains: dict[str, float] = {}  # surplus added by moving just that lever to the benchmark's setting


class GameState(BaseModel):
    ticker: str
    seed: int
    quarter: int = 1  # quarter about to be played; n_quarters() + 1 means finished
    assets: dict[str, float]
    liabilities: dict[str, float]
    annuity_account_value: float  # book value paid on surrender
    guarantee_exposure: float
    guarantee_value: float
    swap_dv01: float = 0  # $bn per 1bp; positive = receive fixed (gains when rates fall)
    uncollateralized_mtm: float = 0  # positive hedge value owed to us by dealers, $bn
    hedges_lost_share: float = 0  # share of hedges gone after a dealer default
    market_rate: float  # current market yield for new money, decimal
    asset_yields: dict[str, float]  # annual yield per asset bucket, scaled to the company's NII yield
    portfolio_yield: float  # the company's net investment yield at the start
    foreign_share: float
    liability_duration_scale: float = 1.0
    alts_beta: float = 0.2
    ig_aaa_share: float = 0.20  # share of investment-grade corporates rated AAA (no credit losses)
    ig_bbb_share: float = 0.45  # share rated BBB; the rest is A-rated
    action: Action = Action()
    prt_decided: bool = False
    history: list[QuarterRecord] = []
    boss_severity: float = 1.0  # set by build_state: the boss shock's strength for this company
