# Surplus or Bust: a Risk Management Simulator

A training game that teaches junior insurance analysts asset liability management (ALM) on six real, publicly traded US life insurers. Each company's balance sheet comes from its latest 10-K on SEC EDGAR, every number in the game is computed by a deterministic engine, and a small team of AI colleagues answers questions using only tools that read that engine.

You run one insurer through five quarters of market stress (rates up, a stock crash, rates down, a junk-bond rout, then a Great Depression boss round). Each quarter you ask your team, sign a trade ticket, watch the market hit, and explain what happened to the Chief Risk Officer, who marks your explanation against the engine's answer key.

*A simplified training simulation for MGT 409E (Yale SOM). Not investment advice and not any company's own risk view.*

## Quick start (Python only, about 5 minutes, no Node needed)

You need **Python 3.11 or newer** and **git**. The built web page is committed, so Python is all you need.

**Windows (PowerShell)**

```
git clone https://github.com/micahwtodd/AI_final_project.git
cd AI_final_project
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

**Mac / Linux**

```
git clone https://github.com/micahwtodd/AI_final_project.git
cd AI_final_project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

`python run.py` opens http://localhost:8000 in your browser. Stop it with Ctrl+C.

### The AI key (optional)

The game plays without a key; only the AI colleagues and Vera's AI marking go offline (a keyword checker marks explanations instead). To turn them on, create a file called `.env` **in the repo folder or one folder up** (the app checks both, this folder first), using `.env.example` as the template:

```
OPENAI_API_KEY=sk-...        # or PORTKEY_API_KEY=... (used first if both are set)
```

The app never prints the key; `run.py` says only whether a key was found and where. Each game has a **$0.25 AI spending cap** (adjustable under *Under the hood*); a typical session measures about **$0.01**.

## A five-minute tour (Demo mode)

1. **Welcome:** click *Let's GOOOOOO*, skim the intro slides (or *Skip intro*).
2. **Pick your insurer:** click **▶ Demo mode**. It plays Jackson Financial on a fixed seed and offers sample answers at every step.
3. **Knowledge Check:** take it (five questions, one at a time, with explanations) or *Skip for now*. The same ideas are asked again at the end.
4. **The desk (Q1):**
   - The **risk dashboard** (left) shows surplus, capital and liquidity ratios with their 100% floors, and the rate mismatch. Hover any underlined label for a plain-English explanation.
   - **Ask your team** (middle): try a demo question. Morty (actuary), Bonnie (portfolio manager) and Swap Dogg (trader) answer in their own bubbles; Vera, the CRO, sums up. *Show chat detail* shows who was asked what, every tool call and its cost.
   - **Trade ticket** (right): drag a slider and watch the dashboard gauges move before you commit. Swaps and puts last one quarter and are cash-settled at its end, so every ticket starts fresh.
5. **Sign trade ticket**, then **End Q1**: make your call on what will hit hardest.
6. **The shock:** the newspaper lands, the dashboard takes its hits, and Vera asks you to name the main two drivers, why they moved surplus, and what your trades did. Click *Use a sample answer (demo)* and submit. The four chips light up as an answer touches each part; *Hint* helps before *I'm not sure*.
7. **Results:** Vera's marked feedback, a scoreboard against doing nothing and "what a pro would do", your shields (what each position did), a what-if replay of the quarter, and a lesson card.
8. Play on to **Q5, the boss round**. Doing nothing all game collapses every company (with a pixel-art explosion); a well-hedged book survives.
9. **The report card:** your grade, a surplus chart against doing nothing and a pro, a quarter-by-quarter record, the skills you showed, and comments from your CRO.

### Under the hood (top-right menu)

- **Trace:** every agent step of the current game: delegations, tool calls and results, tokens and cost per model call.
- **Safety Lab:** prompt-injection attacks (blocked), clean inputs (passed) and teaching-accuracy checks, with pass rates.
- **Experiments:** Solo vs Team, routing vs asking every specialist, 10-K retrieval size, prompt caching, and cost projections (see below).
- **Team / Solo:** Solo mode has Vera answer alone with every tool, for comparison.
- **Budget cap:** change this game's AI spending cap.

## How it works

| Layer | What it does |
|---|---|
| `backend/engine.py` | Deterministic engine: balance sheet, the five shocks, profit and loss by cause, scoring, the answer key. No model calls. |
| `backend/calibration.py`, `sam.py`, `edgar.py`, `filings.py` | Build each company profile from SEC XBRL facts, plus a few figures Seamore (the calibration agent) finds in the 10-K text, each with a quote that code checks against the filing. |
| `backend/agents.py`, `backend/tools.py`, `backend/prompts/` | The AI colleagues (PydanticAI, `gpt-6-luna`): Vera routes questions to specialists, each with read-only tools on the engine; only Swap Dogg can draft a ticket, and only the learner can sign it. |
| `backend/examiner.py` | Vera marks explanations against the engine's answer key (four checks), with a keyword fallback offline. |
| `backend/safety.py` | Input guards before any model sees a message, and sanitizing of filing text. |
| `backend/game.py`, `main.py` | Game sessions and the API (FastAPI). |
| `frontend/` | React + Vite + TypeScript. `frontend/dist` is committed so no Node is needed to play. |

See [`output/harness.md`](output/harness.md) for the agents' tools, memory, stopping rules, guardrails and audit trail. Every model call is logged with its provider-reported tokens and cost in `output/usage_log.jsonl`; every agent step in `output/audit_trail.jsonl` (both git-ignored).

## Measured results (`evidence/experiments.json`)

Run `python scripts/experiments.py` to measure again (about 10 minutes, well under $1). On the last run:

- **E1 Solo vs Team** (ten fixed questions, facts marked by code): Solo 17/19 facts, $0.0004 and 7s per question; Team 19/19 facts and two views on all three decision questions, $0.0012 and 16s.
- **E2** Asking every specialist cost about 1.35 times as much as letting Vera route, with no better facts (19/19 both).
- **E3** Reading 16 chunks per search instead of 4 cost about twice as much and was less reliable: for Jackson the large read did not find the guaranteed-account value at all, and the value the targeted read finds has varied between runs ($174bn and $243bn). Lincoln's values were close.
- **E4** Prompt caching: 92% of input cached with a stable prefix vs 53% with it broken; cost per question cut 50%, facts unchanged.
- **Cost:** a measured full demo game cost $0.0063; a heavier projected session (8 questions) about $0.012, or $0.05 per learner per month on `gpt-6-luna`; the $0.25 cap bounds the worst case.

## Recalibrating the companies

```
python scripts/calibrate_all.py             # SEC XBRL facts + Seamore reading each 10-K (needs a key)
python scripts/calibrate_all.py --tagged    # tagged facts and labelled defaults only (no AI)
python scripts/calibrate_all.py --only JXN  # one company
```

This downloads the filings from SEC EDGAR (cached in `data/cache/`, git-ignored), rebuilds `data/profiles/*.json` with a source for every field, and writes `evidence/calibration_report.json`. SEC asks for a contact string: set `EDGAR_CONTACT=Your Name your@email` in `.env`. The game's tuning can be checked afterwards with `python scripts/tune_engine.py` (doing nothing collapses every company; a pro survives).

## Development

```
pip install -r requirements-dev.txt
python -m pytest -q                                   # 133 tests: engine, API, agents (offline), safety
uvicorn backend.main:app --reload --port 8000         # API with reload
cd frontend && npm install && npm run dev             # UI on http://localhost:5173 (proxies /api)
cd frontend && npm run build                          # rebuild frontend/dist (commit it)
python scripts/tune_engine.py                         # tuning targets across the six companies
python scripts/render_sprites.py                      # redraw the pixel art (Pillow, dev only)
python scripts/safety_lab.py                          # rerun the Safety Lab (needs a key)
python scripts/experiments.py                         # rerun E1 to E4 (needs a key)
```

## Troubleshooting

- **Port 8000 in use (Windows):** `netstat -ano | findstr :8000`, then `taskkill /PID <pid> /F`. Mac: `lsof -i :8000`, then `kill <pid>`.
- **"AI colleagues offline":** no key was found. Check the `.env` file is in the repo folder or one folder up, then restart `python run.py`.
- **A blank page after updating:** hard-refresh the browser (Ctrl+F5 / Cmd+Shift+R).
- **`python` not found on Mac:** use `python3`.

## Data and credits

Company figures come from public SEC filings (10-K, fiscal year 2025) and their XBRL facts; logos are used for identification in a classroom project. Market shocks are stylized on historical episodes (2022, 2000 to 2002, 2019 to 2020, 2015 to 2016, 1929 to 1933). The pixel art is generated in code (`scripts/render_sprites.py`).
