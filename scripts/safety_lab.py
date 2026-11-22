"""Run the Safety Lab (all three tables) and save evidence/safety_lab.json.

Run from the repo folder:  python scripts/safety_lab.py      (needs an API key; costs about $0.03)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import safety_lab  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    r = asyncio.run(safety_lab.run_all())
    a = r["attacks"]
    print(f"ATTACKS  blocked {a['attacks_blocked']}/{a['attacks_total']}   clean passed {a['clean_passed']}/{a['clean_total']}")
    for row in a["rows"]:
        off = row["off"]["outcome"] if row["off"] else "-"
        print(f"  {row['label'][:55]:55} OFF: {off[:45]:45} ON: {row['on']['outcome']}")
    t = r["teaching"]
    print(f"TEACHING {t['correct']}/{t['total']} correct ({t['pass_rate']}%)")
    for row in t["rows"]:
        if not row["correct"]:
            print(f"  MISS {row['id']} {row['concept']}: expected {row['expected']}, got {row['answer']} | {row['reason'][:120]}")
    e = r["examiner"]
    print(f"EXAMINER {e['check_agreement_pct']}% of checks agree; {e['samples_fully_agreeing']}/{e['total']} samples fully agree")
    for row in e["rows"]:
        if not row["all_agree"]:
            print(f"  DIFF {row['id']} {row['kind']}: expected {row['expected']} flag={row['flag_expected']} | got {row['got']} flag={row['flagged']}")
    print(f"TOTAL ${r['total_cost_usd']}  in {r['seconds']}s")


if __name__ == "__main__":
    main()
