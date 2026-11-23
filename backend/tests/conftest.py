"""Tests never call the model: AI features fall back to their offline paths (keyword marker, offline banner)."""

import os

os.environ["SURPLUS_OR_BUST_OFFLINE"] = "1"
