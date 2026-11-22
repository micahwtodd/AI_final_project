"""Project 0 smoke test: one gpt-6-luna call (Portkey, or OpenAI if no Portkey key),
printing reported usage.

Run from the repo folder:  python scripts/smoke_test.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic_ai import Agent, UsageLimits  # noqa: E402

from backend.agents import make_model  # noqa: E402
from backend.env import MODEL_NAME, load_env  # noqa: E402
from backend.pricing import cost_usd  # noqa: E402


def main() -> int:
    status = load_env()
    print(f"Key found: {status.key_found}  provider: {status.provider}  "
          f"name: {status.key_name}  source: {status.key_source}")
    if not status.key_found:
        print("Create .env with PORTKEY_API_KEY=... or OPENAI_API_KEY=... here or one folder up.")
        return 1

    agent = Agent(make_model(), instructions="You are a terse assistant. Reply in one sentence.")
    t0 = time.perf_counter()
    result = agent.run_sync(
        "In one sentence, what is a duration gap for a life insurer?",
        usage_limits=UsageLimits(request_limit=2),
    )
    elapsed = time.perf_counter() - t0
    u = result.usage()

    print(f"\nModel: {MODEL_NAME}   latency: {elapsed:.2f}s")
    print(f"Reply: {result.output}\n")
    print(f"requests           {u.requests}")
    print(f"input_tokens       {u.input_tokens}")
    print(f"cache_read_tokens  {u.cache_read_tokens}")
    print(f"cache_write_tokens {u.cache_write_tokens}")
    print(f"output_tokens      {u.output_tokens}")
    print(f"reasoning_tokens   {u.output_reasoning_tokens}")
    print(f"details            {u.details}")
    cost = cost_usd(u.input_tokens, u.output_tokens, u.cache_read_tokens, u.cache_write_tokens)
    print(f"cost_usd           ${cost:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
