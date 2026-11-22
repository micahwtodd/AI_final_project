"""Company calibration from SEC filings.

Step 1 (code, this file): read tagged XBRL facts and build a CompanyProfile, filling
anything untagged with labelled defaults from data/assumptions.json.
Step 2 (Sam, the Calibration Analyst agent, added in Project 6): read targeted text
from the 10-K for credit quality, rate sensitivity, segment mix and foreign share.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend import edgar
from backend.env import REPO_DIR
from backend.models import ASSET_BUCKETS, LIABILITY_BUCKETS, CompanyProfile, FieldSource

DATA_DIR = REPO_DIR / "data"
PROFILES_DIR = DATA_DIR / "profiles"
TICKERS = ["MET", "PRU", "CRBG", "LNC", "EQH", "JXN"]
DISPLAY_NAMES = {
    "MET": "MetLife", "PRU": "Prudential Financial", "CRBG": "Corebridge Financial",
    "LNC": "Lincoln National", "EQH": "Equitable Holdings", "JXN": "Jackson Financial",
}


def load_assumptions() -> dict:
    return json.loads((DATA_DIR / "assumptions.json").read_text(encoding="utf-8"))


def _tag_candidates() -> dict:
    raw = json.loads((DATA_DIR / "xbrl_tag_candidates.json").read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def _fact(gaap: dict, tag: str, period_end: str, fy: int, duration: bool) -> float | None:
    units = gaap.get(tag, {}).get("units", {}).get("USD", [])
    vals = [
        v for v in units
        if v.get("form") == "10-K" and v.get("end") == period_end and v.get("fy") == fy
        and (("start" in v) == duration)
    ]
    if duration:  # full fiscal year only
        vals = [v for v in vals if v["start"].endswith("-01-01")]
    return vals[-1]["val"] / 1e9 if vals else None


def get_tagged_facts(ticker: str) -> dict[str, FieldSource]:
    """Every candidate field, read from tagged XBRL facts. Missing fields have value None."""
    facts = edgar.company_facts(ticker)
    gaap = facts["facts"]["us-gaap"]
    k = edgar.latest_10k(ticker)
    period_end, fy = k["report_date"], int(k["report_date"][:4])
    out: dict[str, FieldSource] = {}
    for field, spec in _tag_candidates().items():
        found = None
        for tag in spec["tags"]:
            val = _fact(gaap, tag, period_end, fy, spec.get("duration", False))
            if val is not None:
                found = FieldSource(value=round(val, 3), source="tagged",
                                    citation=f"us-gaap:{tag}, 10-K {k['accession']}, period {period_end}")
                break
        out[field] = found or FieldSource(value=None, source="assumption", note="not tagged")
    return out


def build_profile(ticker: str) -> CompanyProfile:
    a = load_assumptions()["defaults_when_untagged"]
    f = get_tagged_facts(ticker)
    k = edgar.latest_10k(ticker)
    v = {name: (fs.value or 0.0) for name, fs in f.items()}
    fields = dict(f)

    def assume(name: str, value: float, note: str) -> float:
        fields[name] = FieldSource(value=round(value, 4), source="assumption", note=note)
        return value

    def derive(name: str, value: float, note: str) -> float:
        fields[name] = FieldSource(value=round(value, 4), source="derived", note=note)
        return value

    invested = derive("invested_assets", v["investments"] + v["cash"],
                      "Investments + cash and cash equivalents")

    # ---- assets ----
    bonds = v["bonds_afs"] + v["bonds_trading"]
    if f["mortgage_loans"].value is None:
        mortgage = assume("mortgage_loans", invested * a["mortgage_share_of_invested"],
                          f"untagged; {a['mortgage_share_of_invested']:.0%} of invested assets")
    else:
        mortgage = v["mortgage_loans"]
    govt_share = assume("govt_share_of_bonds", a["govt_share_of_bonds"], "credit split not tagged; Sam reads it from the filing in Project 6")
    hy_share = assume("below_ig_share_of_bonds", a["below_ig_share_of_bonds"], "credit split not tagged; Sam reads it from the filing in Project 6")
    residual = invested - (bonds + mortgage + v["equity_securities"] + v["other_invested"] + v["cash"])
    derive("residual_invested", residual,
           "policy loans, short-term and other invested assets not tagged separately; treated as investment-grade fixed income")
    raw_assets = {
        "govt": bonds * govt_share,
        "ig_corp": bonds * (1 - govt_share - hy_share) + max(residual, 0.0),
        "below_ig": bonds * hy_share,
        "mortgage": mortgage,
        "equity": v["equity_securities"],
        "alts": v["other_invested"],
        "cash": v["cash"],
    }
    total_raw = sum(raw_assets.values())
    asset_mix = {b: raw_assets[b] / total_raw for b in ASSET_BUCKETS}

    # ---- surplus: equity excluding AOCI ----
    surplus = derive("surplus", v["total_equity"] - v["aoci"],
                     "stockholders' equity excluding AOCI (unrealized bond gains and losses)")

    # ---- liabilities: modeled general account = invested assets - surplus ----
    modeled_liab = invested - surplus
    life_share = assume("life_share_of_fpb", a["life_share_of_future_policy_benefits"],
                        "life vs pension split not tagged; Sam reads segment mix in Project 6")
    mrb_net = v["mrb_liability"] - v["mrb_asset"]
    derive("mrb_net", mrb_net, "market risk benefit liability minus asset (VA guarantees)")
    raw_liab = {
        "annuities": v["policyholder_account_balances"],
        "life": v["future_policy_benefits"] * life_share,
        "prt": v["future_policy_benefits"] * (1 - life_share),
    }
    floor = a["other_liability_floor_share"] * modeled_liab
    room = modeled_liab - mrb_net  # so that invested - liabilities - guarantees = surplus exactly
    if sum(raw_liab.values()) + floor > room:
        scale = (room - floor) / sum(raw_liab.values())
        raw_liab = {b: x * scale for b, x in raw_liab.items()}
        derive("liability_scale", scale, "tagged reserves exceed invested assets less surplus (reinsurance, funds withheld); scaled to fit")
    raw_liab["other"] = room - sum(raw_liab.values())
    total_l = sum(raw_liab.values())
    liability_mix = {b: raw_liab[b] / total_l for b in LIABILITY_BUCKETS}

    guar_share = assume("guaranteed_share_of_sa", a["guaranteed_share_of_separate_accounts"],
                        "share of separate-account value carrying guarantees; not tagged")
    foreign = assume("foreign_share", a["foreign_share"], "not tagged; Sam reads it from the filing in Project 6")
    nii_yield = derive("net_investment_yield", v["net_investment_income"] / invested if invested else 0.045,
                       "net investment income / invested assets")

    return CompanyProfile(
        ticker=ticker, name=DISPLAY_NAMES.get(ticker, ticker), fiscal_year=int(k["report_date"][:4]),
        accession=k["accession"], invested_assets_usd_bn=round(invested, 2), surplus_usd_bn=round(surplus, 2),
        asset_mix={b: round(x, 7) for b, x in asset_mix.items()},
        liability_mix={b: round(x, 7) for b, x in liability_mix.items()},
        guarantee_exposure_usd_bn=round(v["separate_account_assets"] * guar_share, 2),
        guarantee_value_usd_bn=round(mrb_net, 2),
        separate_account_assets_usd_bn=round(v["separate_account_assets"], 2),
        equity_to_assets=round(surplus / invested, 4), net_investment_yield=round(nii_yield, 4),
        rate_sensitivity=None, foreign_share=foreign, fields=fields,
    )


def save_profile(p: CompanyProfile) -> Path:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILES_DIR / f"{p.ticker}.json"
    path.write_text(p.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_profile(ticker: str) -> CompanyProfile:
    return CompanyProfile.model_validate_json((PROFILES_DIR / f"{ticker.upper()}.json").read_text(encoding="utf-8"))


def load_all_profiles() -> list[CompanyProfile]:
    return [load_profile(t) for t in TICKERS if (PROFILES_DIR / f"{t}.json").is_file()]
