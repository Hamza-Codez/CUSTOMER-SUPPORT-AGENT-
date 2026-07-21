"""Test bootstrap: run everything against the mock provider and the mock store.

No API key, no network, no database — the full flow is CI-safe by construction.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# The backend modules import each other flatly (`from store import ...`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Must be set before `model.get_model()` is ever called.
os.environ["MODEL_PROVIDER"] = "mock"


@pytest.fixture(autouse=True)
def clean_tickets():
    """Every test starts with an empty audit trail so ticket counts are exact."""
    import store
    store.reset_tickets()
    yield
    store.reset_tickets()
