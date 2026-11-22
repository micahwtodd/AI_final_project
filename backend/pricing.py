"""Model prices in USD per 1M tokens, from the MGT 409 Lecture 11 table.

Only gpt-6-luna is ever called. The other two are for cost projections.
`input_tokens` reported by the API includes cache reads and cache writes,
so uncached input = input - cache_read - cache_write.
"""

from __future__ import annotations

PRICES = {
    "gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "cache_write": 0.125, "output": 0.50},
    "gpt-6.1-sol": {"input": 2.00, "cached_input": 0.10, "cache_write": 2.50, "output": 10.00},
    "gpt-6-astra": {"input": 10.00, "cached_input": 1.00, "cache_write": 12.50, "output": 50.00},
}


def cost_usd(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    model: str = "gpt-6-luna",
) -> float:
    p = PRICES[model]
    uncached = max(0, input_tokens - cache_read_tokens - cache_write_tokens)
    return (
        uncached * p["input"]
        + cache_read_tokens * p["cached_input"]
        + cache_write_tokens * p["cache_write"]
        + output_tokens * p["output"]
    ) / 1_000_000
