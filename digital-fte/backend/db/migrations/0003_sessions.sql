-- Conversation memory — the FTE's third trait, moved out of process memory.
-- One row per session, rewritten each turn. Messages are the LangChain
-- serialized form (messages_to_dict), stored verbatim as jsonb.

create table if not exists sessions (
  session_id text primary key,
  messages   jsonb       not null default '[]'::jsonb,
  updated_at timestamptz not null default now()
);

-- Sessions are not an audit trail; they are working memory and may be pruned.
-- Nothing prunes them automatically in v1 — a session row lives until it is
-- explicitly cleared. To age them out on a schedule, run something like:
--   delete from sessions where updated_at < now() - interval '30 days';
create index if not exists sessions_updated_at_idx on sessions (updated_at);
