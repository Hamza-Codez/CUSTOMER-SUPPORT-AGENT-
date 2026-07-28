"""Vercel entrypoint.

Vercel's Python runtime looks for a module under `api/` exposing an ASGI app
named `app`, and `vercel.json` rewrites every path onto this one file so FastAPI
keeps doing its own routing. Without the rewrite, Vercel would treat each path as
a separate function and only `/api/index` would exist.

This file deliberately contains no logic. Anything that behaves differently on
Vercel than under `uvicorn` is a difference that will not show up in the test
suite, so the platform seam is kept to an import.

Two things about this runtime that shape the app rather than this file:

- **Instances are ephemeral and plural.** A connection pool is per-instance, so
  it is sized from `DB_POOL_MAX` and the DSN should point at a *transaction*
  pooler. A signing secret generated per process would differ between instances,
  which is why `ENVIRONMENT=production` refuses to start without `JWT_SECRET`.

- **Functions have a wall-clock limit.** An agent turn calls a model two or more
  times and can take tens of seconds. `maxDuration` in `vercel.json` raises the
  ceiling as far as the plan allows; past that the request is killed by the
  platform, and the customer sees the widget's own 45-second timeout message.
  See docs/DEPLOYING.md before assuming this is fine for your traffic.
"""

from __future__ import annotations

from app.main import app

__all__ = ["app"]
