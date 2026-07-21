"""An in-process stand-in for the Supabase client.

It exists so the Supabase code path — query construction, the match_kb_docs RPC,
and above all the row-shape coercion — is tested without credentials.

It deliberately returns rows the way PostgREST does, not the way the mock store
does: `numeric` as a string, `timestamptz` with a +00:00 offset, ids generated
server-side. If `supabase_store` forgot to coerce any of that, the parity tests
fail — which is the entire point.
"""
from __future__ import annotations

import copy
import itertools
from datetime import datetime, timedelta, timezone

import embeddings

_PG_ORDERS = [
    {"order_id": "ORD-1001", "customer": "Jordan Lee",
     "items": ["AeroDesk Standing Desk (oak)"], "total": "499.00",
     "status": "shipped", "carrier": "DHL", "tracking": "DHL-88231145",
     "eta": (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d"),
     "refundable": True, "user_id": None},
    {"order_id": "ORD-1002", "customer": "Priya Nair",
     "items": ["AeroChair Ergonomic Chair"], "total": "329.00",
     "status": "delivered", "carrier": "FedEx", "tracking": "FDX-55190022",
     "eta": (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d"),
     "refundable": True, "user_id": None},
    {"order_id": "ORD-1003", "customer": "Sam Okoro",
     "items": ["AeroDesk Standing Desk (walnut)", "AeroChair Ergonomic Chair"],
     "total": "828.00", "status": "processing", "carrier": None, "tracking": None,
     "eta": (datetime.now(timezone.utc) + timedelta(days=6)).strftime("%Y-%m-%d"),
     "refundable": False, "user_id": None},
]


_SEED_TEMPLATES = [
    {"customer": "You", "items": ["AeroDesk Standing Desk (oak)"], "total": "499.00",
     "status": "shipped", "carrier": "DHL", "tracking": "DHL-88231145",
     "refundable": True, "_eta_days": 2},
    {"customer": "You", "items": ["AeroChair Ergonomic Chair"], "total": "329.00",
     "status": "delivered", "carrier": "FedEx", "tracking": "FDX-55190022",
     "refundable": True, "_eta_days": -1},
    {"customer": "You", "items": ["AeroDesk Standing Desk (walnut)"], "total": "828.00",
     "status": "processing", "carrier": None, "tracking": None,
     "refundable": False, "_eta_days": 6},
]


class _Result:
    def __init__(self, data):
        self.data = data


class _TableQuery:
    """Emulates the PostgREST builder chain used by supabase_store."""

    def __init__(self, db, table):
        self._db = db
        self._table = table
        self._rows = None
        self._filters = []
        self._orders = []
        self._limit = None
        self._insert = None
        self._upsert = None
        self._conflict = None
        self._delete = False

    def select(self, _columns="*"):
        self._rows = list(self._db.tables[self._table])
        return self

    def eq(self, column, value):
        self._filters.append((column, value))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def order(self, column, desc=False):
        self._orders.append((column, desc))
        return self

    def insert(self, row):
        self._insert = row
        return self

    def upsert(self, row, on_conflict=None):
        self._upsert = row if isinstance(row, list) else [row]
        self._conflict = on_conflict
        return self

    def delete(self):
        self._delete = True
        return self

    def execute(self):
        if self._insert is not None:
            return _Result([self._db.insert(self._table, self._insert)])

        if self._upsert is not None:
            return _Result([self._db.upsert(self._table, row, self._conflict)
                            for row in self._upsert])

        if self._delete:
            kept, removed = [], []
            for row in self._db.tables[self._table]:
                match = all(row.get(c) == v for c, v in self._filters)
                (removed if match else kept).append(row)
            self._db.tables[self._table] = kept
            return _Result(removed)

        rows = self._rows if self._rows is not None else list(self._db.tables[self._table])
        for column, value in self._filters:
            rows = [r for r in rows if r.get(column) == value]
        # Applied in reverse so the first .order() call is the primary key.
        for column, desc in reversed(self._orders):
            rows.sort(key=lambda r: r.get(column) or "", reverse=desc)
        if self._limit is not None:
            rows = rows[:self._limit]
        # A real query returns values parsed from a JSON response, never
        # references into the server's storage. Copy, so a caller mutating a
        # fetched row cannot reach back into this table.
        return _Result(copy.deepcopy(rows))


class _Rpc:
    def __init__(self, db, name, params):
        self._db = db
        self._name = name
        self._params = params

    def execute(self):
        if self._name == "match_kb_docs":
            return _Result(self._db.match_kb_docs(**self._params))
        if self._name == "seed_demo_orders":
            return _Result(self._db.seed_demo_orders(**self._params))
        raise KeyError(f"No such RPC: {self._name}")


class FakeSupabase:
    """Minimal Postgres stand-in: three orders, an empty ticket log, an embedded KB."""

    def __init__(self, kb_docs):
        self._ticket_seq = itertools.count(1)
        self._order_seq = itertools.count(2001)
        self.tables = {
            "orders": [dict(o) for o in _PG_ORDERS],
            "tickets": [],
            "kb_docs": [],
            "sessions": [],
        }
        vectors = embeddings.embed([f"{d['title']} {d['body']}" for d in kb_docs])
        for doc, vector in zip(kb_docs, vectors):
            self.tables["kb_docs"].append(
                {"title": doc["title"], "body": doc["body"], "embedding": vector}
            )

    # --- server-side behaviour the schema defines ---
    def insert(self, table, row):
        stored = dict(row)
        if table == "tickets":
            stored.setdefault("id", f"TCK-{next(self._ticket_seq):04d}")
            stored.setdefault("status", "open")
            stored.setdefault("priority", "normal")
            stored.setdefault("escalated", False)
            # PostgREST renders timestamptz with an explicit offset.
            stored.setdefault(
                "created_at",
                datetime.now(timezone.utc).isoformat(timespec="seconds").replace("Z", "+00:00"),
            )
        self.tables[table].append(stored)
        return stored

    def upsert(self, table, row, on_conflict=None):
        stored = copy.deepcopy(row)          # Postgres stores a value, not a reference
        key = on_conflict or "id"
        for index, existing in enumerate(self.tables[table]):
            if existing.get(key) == stored.get(key):
                self.tables[table][index] = stored
                return stored
        self.tables[table].append(stored)
        return stored

    def seed_demo_orders(self, p_user_id):
        """Mirrors the plpgsql function in 0004: idempotent, ids from a sequence."""
        mine = [o for o in self.tables["orders"] if o.get("user_id") == p_user_id]
        if not mine:
            for template in _SEED_TEMPLATES:
                row = dict(template)
                row["order_id"] = f"ORD-{next(self._order_seq):04d}"
                row["user_id"] = p_user_id
                row["eta"] = (datetime.now(timezone.utc)
                              + timedelta(days=row.pop("_eta_days"))).strftime("%Y-%m-%d")
                self.tables["orders"].append(row)
            mine = [o for o in self.tables["orders"] if o.get("user_id") == p_user_id]
        return copy.deepcopy(sorted(mine, key=lambda o: o["order_id"]))

    def match_kb_docs(self, query_embedding, match_count=3, min_similarity=0.05):
        scored = []
        for row in self.tables["kb_docs"]:
            similarity = sum(a * b for a, b in zip(query_embedding, row["embedding"]))
            if similarity >= min_similarity:
                scored.append({"title": row["title"], "body": row["body"],
                               "similarity": similarity})
        scored.sort(key=lambda r: r["similarity"], reverse=True)
        return scored[:match_count]

    # --- client surface ---
    def table(self, name):
        return _TableQuery(self, name)

    def rpc(self, name, params):
        return _Rpc(self, name, params)
