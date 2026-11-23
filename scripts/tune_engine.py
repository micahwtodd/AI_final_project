"""Check the engine's tuning targets across the six companies (seed 409 by default).

Targets (five-quarter campaign, Gate 1 feedback), checked for each company:
  1. Doing nothing all game collapses the company (surplus at or below zero after the boss round).
  2. A pro (the benchmark trades) survives, losing under 60%.
  3. Hedging everything to the maximum scores below the benchmark (cost).
  4. No single lever wins alone (each single-lever strategy scores below the benchmark).

Run:  python scripts/tune_engine.py [--seed 409] [--detail MET]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import engine  # noqa: E402
from backend.calibration import load_all_profiles  # noqa: E402
from backend.models import Action  # noqa: E402

MAX = Action(rate_hedge_pct=120, credit_shift_pct=50, equity_hedge_pct=100,
             cash_buffer_pct=15, collateralized=True, dealers=3, accept_prt=False)


def single_levers(start_cash: float) -> dict[str, Action]:
    base = dict(cash_buffer_pct=start_cash, collateralized=False, dealers=1)
    return {
        "rate only": Action(**{**base, "rate_hedge_pct": 80}),
        "credit only": Action(**{**base, "credit_shift_pct": 20}),
        "equity only": Action(**{**base, "equity_hedge_pct": 60}),
        "cash only": Action(**{**base, "cash_buffer_pct": 8}),
    }


def run(profile, seed: int, strategy) -> tuple[float, float, list]:
    """strategy: None (do nothing), 'benchmark', or a fixed Action used every quarter."""
    s = engine.build_state(profile, seed)
    s0 = engine.surplus(s)
    for q in range(1, engine.n_quarters() + 1):
        card = engine.card_for(q)
        if strategy is None:
            act = None
        elif strategy == "benchmark":
            act = card.benchmark_action
        else:
            act = strategy
        s, _ = engine.play_quarter(s, act)
    loss_pct = 100 * (engine.surplus(s) - s0) / s0
    return loss_pct, engine.score(s.history)["results_score"], s.history


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=409)
    ap.add_argument("--detail", default=None)
    args = ap.parse_args()

    hits = [0, 0, 0, 0]
    profiles = load_all_profiles()
    print(f"seed {args.seed}   (surplus change over {engine.n_quarters()} quarters; score 0-100)")
    print(f"{'':5} {'nothing%':>9} {'bench%':>8} {'bench sc':>8} {'max%':>7} {'max sc':>7}  single-lever scores")
    for p in profiles:
        n_pct, n_sc, n_hist = run(p, args.seed, None)
        b_pct, b_sc, b_hist = run(p, args.seed, "benchmark")
        m_pct, m_sc, _ = run(p, args.seed, MAX)
        start_cash = engine.build_state(p, args.seed).action.cash_buffer_pct
        singles = {k: run(p, args.seed, a)[1] for k, a in single_levers(start_cash).items()}
        t = [n_pct <= -100, b_pct > -60, m_sc < b_sc, all(v < b_sc for v in singles.values())]
        hits = [h + int(x) for h, x in zip(hits, t)]
        marks = "".join("Y" if x else "." for x in t)
        sl = " ".join(f"{k.split()[0]}:{v:.0f}" for k, v in singles.items())
        print(f"{p.ticker:5} {n_pct:9.1f} {b_pct:8.1f} {b_sc:8.1f} {m_pct:7.1f} {m_sc:7.1f}  {sl}   [{marks}]")
        if args.detail and args.detail.upper() == p.ticker:
            for label, hist in (("NOTHING", n_hist), ("BENCHMARK", b_hist)):
                print(f"  {label}")
                for r in hist:
                    comps = " ".join(f"{k[:6]}:{v:+.2f}" for k, v in r.attribution.components().items())
                    print(f"   Q{r.quarter} sev {r.severity} dS {r.surplus_after - r.surplus_before:+.2f}  {comps}")
    print(f"\ntargets met (of {len(profiles)}): nothing collapses: {hits[0]}  pro survives (<60% loss): {hits[1]}  "
          f"max below benchmark: {hits[2]}  no single lever wins: {hits[3]}")


if __name__ == "__main__":
    main()
