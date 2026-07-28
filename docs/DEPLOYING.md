# Deploying the backend

Written for Vercel, because that is what was asked for. Read the fit section
first — the answer is "yes, with one real caveat", and knowing the caveat before
you deploy is cheaper than discovering it from a customer.

---

## Is Vercel the right host for this?

Mostly yes. The awkward part is time.

A single chat turn calls the model **at least twice** — once to route, once for
the specialist — plus retrieval and a database round trip. Against real Gemini
that is commonly **10–30 seconds**, and the frontend's own client timeout is set
to 45 for that reason. Vercel functions have a wall-clock ceiling that depends on
your plan; `vercel.json` asks for `maxDuration: 60`, and Vercel will silently
clamp that to whatever your plan actually allows. If a turn exceeds it the
platform kills the request mid-flight and the customer sees the widget's timeout
message.

What that means in practice:

- **Fine** for the marketing site, the dashboard, `widget.js`, site keys, the
  feedback links, and demo traffic on the mock provider.
- **Watch** real Gemini turns under load. If you see the widget timing out, the
  function limit is the first thing to check, not the model.
- If turn latency becomes a problem, a container host with no request ceiling
  (Render, Railway, Fly) runs this unchanged — it is a plain ASGI app, and
  nothing in it is Vercel-specific except `api/index.py` and `vercel.json`.

Two other platform facts shaped the code rather than the config:

- **Instances are ephemeral and plural.** Each one has its own connection pool
  and its own memory, so anything generated per process differs between them.
  That is why an unset `JWT_SECRET` is a startup failure in production rather
  than a warning — sign-ins would fail at random as requests landed on different
  instances.
- **The filesystem is read-only** apart from `/tmp`. Nothing here writes files.

---

## The production guard

`ENVIRONMENT=production` refuses to start on any configuration that would fail
*quietly*. Every default in this app is chosen so it boots with zero setup, and
each of those defaults is wrong in public:

| Default | Why it must not ship |
|---|---|
| `MODEL_PROVIDER=mock` | Answers from a lookup table and looks entirely healthy |
| no `DATABASE_URL` | In-memory store: every instance a different empty database |
| generated `JWT_SECRET` | Differs per instance; sign-ins fail at random |
| `DEV_TOKENS` demo values | **`ops-token` grants operator access.** A documented, guessable string that reaches the refund queue |
| `ALLOWED_ORIGINS=*` | Bearer-token dashboard routes callable from any page |
| `PUBLIC_BASE_URL=http://localhost:8000` | Baked into `widget.js` and email links |

It reports **all** of them at once, so you fix the list rather than redeploying
per variable. To see it before you deploy:

```bash
cd backend
ENVIRONMENT=production uv run python -c \
  "from app.core.config import Settings; [print('-', p) for p in Settings().deployment_problems()]"
```

Note the `DEV_TOKENS` consequence honestly: **clearing them breaks the seeded
`/demo` playground**, which authenticates with exactly those strings. That is the
correct trade for a public deployment; if you want the demo live, give it its own
tenant and its own unguessable tokens.

---

## Steps

### 1. Point the DSN at a transaction pooler

Serverless means many instances, each with its own pool. A direct Postgres
connection limit is reached quickly that way. On Supabase use the **transaction
pooler** (port **6543**), not the direct connection (5432), and tell asyncpg:

```
DATABASE_URL=postgresql://user:pass@host:6543/postgres
DB_TRANSACTION_POOLER=true
DB_POOL_MAX=3
```

`DB_TRANSACTION_POOLER=true` sets `statement_cache_size=0`. Without it you get
intermittent `prepared statement "_asyncpg_stmt_N" does not exist` — a failure
that never appears in testing, because it needs two clients sharing one backend
connection.

URL-encode the password. A raw `#` truncates the URL and the port parses as
garbage.

### 2. Apply the schema

Run once from your machine, against the **direct** connection (5432), not the
pooler — DDL and the `vector` extension want a real session:

```bash
cd backend
uv run python scripts/init_db.py
```

### 3. Set the environment variables

In Vercel → Project → Settings → Environment Variables:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | pooler DSN, password URL-encoded |
| `DB_TRANSACTION_POOLER` | `true` |
| `DB_POOL_MAX` | `3` |
| `MODEL_PROVIDER` | `gemini` |
| `GEMINI_API_KEY` | your key |
| `EMBEDDING_PROVIDER` | `gemini` |
| `JWT_SECRET` | `openssl rand -base64 48` |
| `DEV_TOKENS` | empty |
| `ALLOWED_ORIGINS` | `https://your-frontend.vercel.app` (comma-separated) |
| `PUBLIC_BASE_URL` | `https://your-api.vercel.app` |
| `BUSINESS_DISPLAY_NAME` | your store |

`PUBLIC_BASE_URL` is chicken-and-egg on a first deploy: you do not know the URL
until it exists. Deploy once with a placeholder, then set it and redeploy — it is
compiled into `widget.js` and into email links, so a wrong value is a widget that
cannot reach its own API.

### 4. Deploy

Set the Vercel **root directory to `backend/`**. It contains `vercel.json`,
`requirements.txt` and `api/index.py`, and that is all Vercel needs.

`requirements.txt` is generated from `uv.lock`, so the deployed versions are the
tested versions. Regenerate after any dependency change:

```bash
cd backend
uv export --no-dev --no-hashes --no-emit-project --format requirements-txt -o requirements.txt
```

### 5. Check it

Open the bare URL first. It answers:

```json
{"service":"Digital FTE — Agent Platform","version":"0.3.0","docs":"/docs","health":"/health"}
```

If you instead see `{"detail":"Not Found"}`, that is FastAPI's own 404 rather
than Vercel's HTML one — which means the rewrite worked and the app is running,
you have simply hit a path it does not serve. Check `/health`.

```bash
curl -s https://your-api.vercel.app/health
# {"status":"ok","provider":"gemini","store":"postgres","db":"up"}
```

`provider` must read `gemini` and `store` must read `postgres`. If either says
`mock`, the environment variables did not reach the function — and the guard
should have refused the boot, so check the deployment logs for the refusal.

Then:

```bash
curl -sI https://your-api.vercel.app/widget.js | head -3
curl -s -X POST https://your-api.vercel.app/chat/public \
  -H 'Content-Type: application/json' -H 'X-FTE-Site-Key: pk_...' \
  -H 'Origin: https://yourstore.com' \
  -d '{"message":"hi","session_id":"deploy-check"}'
```

Time that last one. It is your real turn latency against the function ceiling.

---

## Verified

Probed locally on 2026-07-28 against the real Supabase database:

| What | Result |
|---|---|
| `api/index.py` imports and serves as an ASGI app | 28 routes, `/` and `/health` 200 |
| Boot under a full production config | starts, `provider=gemini store=postgres` |
| `DB_TRANSACTION_POOLER=true` against a live server | accepted |
| `ops-token` on the operator queue in production | **401** |
| CORS preflight from an unlisted origin | **400** |
| CORS preflight from a listed origin | 200, origin echoed |
| `widget.js` carries `PUBLIC_BASE_URL`, not localhost | confirmed |
| Guard lists every problem at once | 446 tests, 23 of them this |

## Not verified

**Nothing has been deployed to Vercel.** There is no Vercel account in this
environment. `vercel.json`, `api/index.py` and `requirements.txt` are written to
Vercel's documented contract and the app they point at is verified to boot and
serve — but the build itself, the cold-start time, the function size against
Vercel's 250 MB limit, and the real `maxDuration` your plan grants are all
unmeasured. Expect the first deploy to surface something.
