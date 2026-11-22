"""Tests never call the model: AI features fall back to their offline paths (keyword marker, offline banner)."""

import os

os.environ["RISK_DESK_OFFLINE"] = "1"
