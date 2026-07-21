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

# Must be set before `model.get_model()` / `store._backend()` are ever called.
os.environ["MODEL_PROVIDER"] = "mock"
os.environ.setdefault("DATA_BACKEND", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "mock")
os.environ.setdefault("AUTH_PROVIDER", "mock")
# The mock model paces its simulated stream for demos; tests want it instant.
os.environ.setdefault("MOCK_STREAM_DELAY_MS", "0")


@pytest.fixture(autouse=True)
def clean_tickets():
    """Every test starts with an empty audit trail so ticket counts are exact.

    Resets the mock backend directly rather than through the facade: the
    Supabase backend refuses reset_tickets() on purpose (it would delete a real
    audit log), and parity tests get a fresh fake per case instead.
    """
    from store import mock_store
    mock_store.reset_tickets()
    yield
    mock_store.reset_tickets()
