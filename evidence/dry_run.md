# Fresh-clone dry run (Project 11)

Run on 2026-11-23, Windows 11, Python 3.14.7, git 2.55. A clean `git clone` of the repo into a new folder, with `.env` one folder up (the parent of the clone), following the README's Python-only quick start.

| Step | Time |
|---|---|
| `git clone` | under 1 s |
| `python -m venv .venv` | 5 s |
| `pip install -r requirements.txt` | 27 s |
| Start the server and pass the checks below | about 8 s |
| **Total, clone to a working game** | **about 40 s** (target: under 10 minutes) |

Checks against the fresh clone's server:

- `/api/health`: 200, key found (in the parent folder), model `gpt-6-luna`
- `/` (the committed `frontend/dist`): 200, no Node needed
- `/api/companies`: all 6 company profiles load
- `POST /api/game` (Jackson, seed 409): a game starts at Q1 of 5, "The Inflation Surprise"
- `/api/experiments`: the committed results are served

Note: the check ran the server with `uvicorn backend.main:app --port 8011` because port 8000 was in use by the development server; `python run.py` starts the same app on port 8000 and opens the browser.
