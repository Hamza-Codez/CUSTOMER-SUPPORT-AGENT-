-- Fix: vector search returned zero rows on a correctly-populated table.
--
-- 0001 created an ivfflat index with lists = 100 while kb_docs was still empty.
-- ivfflat is a *trained* index: it clusters existing rows into `lists` cells and
-- a query probes only `ivfflat.probes` of them (default 1). Built on an empty
-- table, the centroids are degenerate; with 5 rows and 100 lists, the one list a
-- query probes is almost certainly empty — so a perfectly good match is never
-- looked at and the KB appears to contain nothing.
--
-- HNSW is not trained. It builds incrementally as rows arrive, needs no minimum
-- row count, and gives exact-ish recall at this size. For a knowledge base of
-- hundreds-to-thousands of passages it is simply the right choice.

drop index if exists kb_docs_embedding_idx;

create index if not exists kb_docs_embedding_hnsw
  on kb_docs using hnsw (embedding vector_cosine_ops);

-- Recreated so similarity is computed once and NULL can never silently filter
-- every row: an uncastable query_embedding used to make the comparison NULL,
-- which is not true, which returned nothing — indistinguishable from "no match".
create or replace function match_kb_docs(
  query_embedding vector(1536),
  match_count     int   default 3,
  min_similarity  float default 0.05
)
returns table (title text, body text, similarity float)
language sql stable
as $$
  select d.title, d.body, s.similarity
  from kb_docs d
  cross join lateral (
    select 1 - (d.embedding <=> query_embedding) as similarity
  ) s
  where d.embedding is not null
    and query_embedding is not null
    and s.similarity >= min_similarity
  order by s.similarity desc
  limit match_count;
$$;
