"""Environment loading, and a guard against committing a real credential.

`.env.example` is tracked by git; `.env` is not. A key pasted into the template
would be committed and pushed, so the last test here fails loudly if that ever
happens again.
"""
from __future__ import annotations

import os
from pathlib import Path

import config

BACKEND_DIR = Path(__file__).resolve().parent.parent
EXAMPLE = BACKEND_DIR / ".env.example"

# Anything here is a credential, never a value a template should carry.
SECRET_KEYS = [
    "SUPABASE_SERVICE_KEY", "SUPABASE_JWT_SECRET", "SUPABASE_ANON_KEY",
    "OPENAI_API_KEY", "SUPABASE_URL",
]


def _assignments(text: str) -> dict[str, str]:
    """Uncommented KEY=VALUE pairs only — commented examples are fine."""
    found = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        found[key.strip()] = value.strip().strip('"').strip("'")
    return found


def test_env_example_carries_no_real_credentials():
    """If this fails: move the values to .env (gitignored) and run
    `git checkout -- digital-fte/backend/.env.example`."""
    assigned = _assignments(EXAMPLE.read_text(encoding="utf-8"))

    leaked = [k for k in SECRET_KEYS if assigned.get(k)]
    assert not leaked, (
        f"{leaked} has a value in the tracked template .env.example. "
        "Put real credentials in .env instead — .env.example is committed."
    )


def test_env_example_keeps_the_zero_setup_defaults():
    """A template that ships DATA_BACKEND=supabase would break the promise that
    a fresh clone runs with no external services."""
    assigned = _assignments(EXAMPLE.read_text(encoding="utf-8"))
    for key in ("MODEL_PROVIDER", "DATA_BACKEND", "EMBEDDING_PROVIDER"):
        assert assigned.get(key) == "mock", f"{key} should default to mock"


def test_loading_never_overrides_an_existing_variable(tmp_path, monkeypatch):
    """Shell vars, CI settings and the test suite must always beat the file."""
    monkeypatch.setenv("DATA_BACKEND", "mock")
    env_file = tmp_path / ".env"
    env_file.write_text("DATA_BACKEND=supabase\nA_FRESH_KEY=from-file\n", encoding="utf-8")

    assert config.load_env(env_file) is True
    assert os.environ["DATA_BACKEND"] == "mock"          # not clobbered
    assert os.environ["A_FRESH_KEY"] == "from-file"      # but gaps are filled


def test_a_missing_env_file_is_not_an_error(tmp_path):
    assert config.load_env(tmp_path / "nope.env") is False
