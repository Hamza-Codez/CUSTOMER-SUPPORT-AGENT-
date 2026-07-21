"""Environment loading — one place, imported before anything reads os.getenv.

SPEC §11 tells you to `cp .env.example .env`, but nothing used to read that
file: every provider switch defaulted to `mock`, so it never showed. The moment
real credentials were needed, `.env` turned out to be inert.

`override=False` is deliberate: a variable already in the environment always
wins over the file. So `$env:VAR=...`, CI settings and the test suite's own
config beat `.env`, and the file only fills in what nothing else has set.
"""
from __future__ import annotations

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
ENV_FILE = BACKEND_DIR / ".env"


def load_env(path: Path | None = None) -> bool:
    """Load .env if present. Returns whether a file was found."""
    target = path or ENV_FILE
    if not target.is_file():
        return False
    try:
        from dotenv import load_dotenv
    except ImportError:      # pragma: no cover - dotenv is in requirements
        return False
    load_dotenv(target, override=False)
    return True


loaded = load_env()
