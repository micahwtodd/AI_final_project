# Risk Desk

A training game that teaches junior insurance analysts asset liability management on real, publicly traded life insurers. Balance sheets come from each company's latest 10-K on SEC EDGAR; every number in the game is computed by a deterministic engine.

*Work in progress. The full guide, Demo mode and a five-minute tour come with the finished build.*

## Quick start (Python only, no Node needed)

```
python -m venv .venv
.venv\Scripts\activate            (Mac: source .venv/bin/activate)
pip install -r requirements.txt
python run.py                     -> http://localhost:8000
```

Put `PORTKEY_API_KEY=...` or `OPENAI_API_KEY=...` in `.env` in this folder or one folder up. Without a key the game still plays; the AI colleagues are offline.

## Development

```
pip install -r requirements-dev.txt
python -m pytest -q                                   # engine and API tests
uvicorn backend.main:app --reload --port 8000         # API
cd frontend && npm install && npm run dev             # UI on http://localhost:5173 (proxies /api)
cd frontend && npm run build                          # rebuild frontend/dist (commit it)
python scripts/calibrate_all.py                       # rebuild the six company profiles from SEC EDGAR
python scripts/tune_engine.py                         # check the engine's tuning targets
```

Stuck port on Windows: `netstat -ano | findstr :8000`, then `taskkill /PID <pid> /F`.
