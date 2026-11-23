"""Play Risk Desk in Demo mode in a real browser and screenshot each step (dev only).

Needs the server running on http://localhost:8000 and `pip install playwright` (uses the installed Microsoft Edge,
so no browser download). Run 1 plays the pro's tickets with team questions; run 2 does nothing to show the collapse.

    python scripts/capture_evidence.py            # both runs
    python scripts/capture_evidence.py --only 2   # just the collapse run

Screenshots go to evidence/screens/, and the run's game ids to evidence/screens/runs.json.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = "http://localhost:8000"
OUT = Path("evidence/screens")
PRED = {1: "Rates jump", 2: "Stocks crash", 3: "Rates fall", 4: "Bonds default", 5: "Everything at once"}
CARDS = json.loads(Path("data/events.json").read_text(encoding="utf-8"))["cards"]
PRO = {i + 1: c["benchmark_action"] for i, c in enumerate(CARDS)}
LEVERS = ["rate_hedge_pct", "credit_shift_pct", "equity_hedge_pct", "cash_buffer_pct"]
QUESTION = "What is our biggest risk right now?"
ISIN = "Should we sell bond US0378331005 to raise cash?"

SET_RANGE = """([id, v]) => { const el = document.getElementById(id); if (!el) return false;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, String(v));
  el.dispatchEvent(new Event('input', { bubbles: true })); return true; }"""


def settle(page: Page, s: float = 1.2):
    try:
        page.wait_for_load_state("networkidle", timeout=90_000)
    except Exception:
        pass
    time.sleep(s)


def shot(page: Page, name: str, full: bool = False, el: str | None = None):
    path = OUT / f"{name}.png"
    if el and page.locator(el).count():
        page.locator(el).first.screenshot(path=str(path))
    else:
        page.screenshot(path=str(path), full_page=full)
    print("  shot", path.name)


def click(page: Page, text: str, exact: bool = False, timeout: int = 15_000, optional: bool = False) -> bool:
    loc = page.get_by_role("button", name=text, exact=exact)
    try:
        loc.first.wait_for(state="visible", timeout=timeout)
        loc.first.click()
        settle(page, 0.8)
        return True
    except Exception:
        if optional:
            return False
        names = [b.inner_text()[:50] for b in page.get_by_role("button").all() if b.is_visible()]
        shot(page, "_stuck")
        raise SystemExit(f"could not click {text!r}; visible buttons: {names}")


def ask(page: Page, q: str):
    box = page.get_by_label("Question for your colleagues")
    box.fill(q)
    with page.expect_response(lambda r: "/ask" in r.url, timeout=120_000) as resp:
        page.get_by_role("button", name="Ask", exact=True).click()
    resp.value.finished()
    page.wait_for_function("() => !document.querySelector('.ask-row input')?.disabled", timeout=120_000)
    settle(page, 3)


def set_ticket(page: Page, gid: str, q: int):
    view = page.request.get(f"{BASE}/api/game/{gid}").json()
    pos, pro = view["action"], PRO[q]
    for k in LEVERS:
        delta = round(pro[k] - pos[k], 2)
        if delta:
            page.evaluate(SET_RANGE, [k, delta])
    box = page.get_by_label("Daily collateral")
    if box.is_checked() != pro["collateralized"]:
        box.click()
    page.locator("select").first.select_option(str(pro["dealers"]))
    settle(page, 1.5)


def play_quarter(page: Page, gid: str, q: int, trade: bool, first_run: bool):
    settle(page, 2)
    if first_run and q == 1:
        shot(page, "04_desk_q1")
    click(page, "Hide guide", optional=True, timeout=2000)
    if first_run and q == 1:
        ask(page, QUESTION)
        shot(page, "05_team_answer", el=".chat-panel, .panel.chat")
        ask(page, ISIN)
        shot(page, "06_isin_blocked", el=".chat-panel, .panel.chat")
    if trade:
        set_ticket(page, gid, q)
        if first_run and q in (1, 3):
            shot(page, f"07_ticket_q{q}")
        click(page, "Sign trade ticket")
    click(page, f"End Q{q}")
    if first_run and q == 1:
        shot(page, "08_predict")
    if trade:
        page.locator(".predict-opt", has_text=PRED[q]).first.click()
    else:
        click(page, "Skip and end the quarter")
    settle(page, 6)
    shot(page, f"{'09' if first_run else '19'}_shock_q{q}")
    click(page, "Call her over now", optional=True, timeout=3000)
    if not click(page, "Use a sample answer (demo)", optional=True, timeout=8000):
        page.locator("textarea").first.fill("Rates moved our surplus because our liabilities are longer than our assets.")
    with page.expect_response(lambda r: r.url.endswith("/explain"), timeout=120_000):
        click(page, "Submit explanation")
    settle(page, 3)
    if first_run:
        shot(page, f"10_vera_q{q}")
    if page.get_by_role("button", name="Submit second try").count():
        page.locator("textarea").first.fill(
            "The biggest move was what our hedges left exposed: stocks and credit as well as rates. Our swaps and puts "
            "offset most of the rate and stock losses, so the remaining hit came from the risk we did not hedge.")
        with page.expect_response(lambda r: r.url.endswith("/explain"), timeout=120_000):
            click(page, "Submit second try")
        settle(page, 3)
    for i, beat in enumerate(("See the scoreboard", "How would a pro have traded?", "Collect your lesson card")):
        if click(page, beat, optional=True, timeout=6000) and first_run and q in (1, 2):
            settle(page, 1.5)
            shot(page, f"11_q{q}_beat{i + 1}")
    nxt = "See the final debrief" if q == 5 else ("Prepare for the boss round" if q == 4 else f"On to Q{q + 1}")
    if not click(page, nxt, optional=True, timeout=8000):
        click(page, "Survey the wreckage", timeout=20_000)


def new_game(page: Page) -> str:
    page.goto(BASE)
    settle(page)
    return ""


def run(pw, n: int, runs: dict):
    browser = pw.chromium.launch(channel="msedge", headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    page = ctx.new_page()
    page.emulate_media(reduced_motion="no-preference", color_scheme="light")
    gid = {}

    def grab(r):
        if r.url.endswith("/api/game") and r.request.method == "POST":
            try:
                gid["id"] = r.json()["id"]
            except Exception:
                pass
    page.on("response", grab)
    first = n == 1
    page.goto(BASE)
    settle(page)
    if first:
        shot(page, "01_welcome")
    click(page, "Let's GOOOOOO")
    click(page, "Skip intro", optional=True, timeout=5000)
    settle(page)
    if first:
        shot(page, "02_companies")
    click(page, "Demo mode")
    settle(page, 2)
    click(page, "Take the Knowledge Check", optional=True, timeout=4000)
    if first:
        shot(page, "03_knowledge_check")
    if not click(page, "Skip the quiz", optional=True, timeout=6000):
        page.get_by_text("Skip the quiz").first.click()
        settle(page)
    click(page, "Skip for now", optional=True, timeout=3000)
    for q in range(1, 6):
        print(f"run {n} Q{q}")
        play_quarter(page, gid["id"], q, trade=first, first_run=first)
        if not first and page.get_by_text("collapsed", exact=False).count() and q < 5:
            pass
    settle(page, 4)
    shot(page, "12_report_card" if first else "20_collapse_report", full=True)
    runs[f"run{n}"] = gid.get("id")
    if first:
        for item, name in (("Trace", "13_trace"), ("Experiments", "14_experiments"), ("Safety Lab", "15_safety_lab")):
            click(page, "Under the hood")
            page.get_by_role("menuitem", name=item).first.click()
            settle(page, 2.5)
            shot(page, name, full=True)
            click(page, "← Back", optional=True, timeout=3000)
    browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    runs_path = OUT / "runs.json"
    runs = json.loads(runs_path.read_text()) if runs_path.exists() else {}
    with sync_playwright() as pw:
        for n in (1, 2):
            if a.only and n != a.only:
                continue
            run(pw, n, runs)
            runs_path.write_text(json.dumps(runs, indent=2))
    print("done", runs)


if __name__ == "__main__":
    main()
