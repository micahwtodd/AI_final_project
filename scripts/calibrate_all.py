"""Build the six cached company profiles from SEC tagged facts.

Run from the repo folder:  python scripts/calibrate_all.py
Writes data/profiles/{TICKER}.json. Raw SEC downloads are cached in data/cache/ (git-ignored).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.calibration import TICKERS, build_profile, save_profile  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{'':5} {'invested':>9} {'surplus':>8} {'S/A':>6} {'NII yld':>7}  asset mix / liability mix")
    for t in TICKERS:
        p = build_profile(t)
        save_profile(p)
        am = " ".join(f"{k}:{v:.0%}" for k, v in p.asset_mix.items())
        lm = " ".join(f"{k}:{v:.0%}" for k, v in p.liability_mix.items())
        print(f"{t:5} {p.invested_assets_usd_bn:9.1f} {p.surplus_usd_bn:8.1f} {p.equity_to_assets:6.1%} "
              f"{p.net_investment_yield:7.2%}  {am}\n{'':41}{lm}  guar:{p.guarantee_exposure_usd_bn:.0f} mrb:{p.guarantee_value_usd_bn:.1f}")


if __name__ == "__main__":
    main()
