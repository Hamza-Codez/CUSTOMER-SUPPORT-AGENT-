# Knowledge base — put your real documents here

Every `.md` / `.txt` file in this folder becomes what the agent answers from.
Replace the sample files below with your actual FAQ, policy and product docs.

## How a document is turned into answers

- `# Heading` on the first line names the document.
- Each `## Heading` becomes its own retrievable passage, titled
  "Document — Section", so an answer can say where it came from.
- A document with no `##` sections is kept whole.
- Anything longer than ~1200 characters is split on paragraph boundaries.

Passages, not whole files, because a long document embedded as one vector
retrieves badly — the relevant paragraph gets averaged away by the rest.

## After you change anything here

```bash
# mock backend: nothing to do, it reads this folder on start
# supabase backend: re-embed and reload
python scripts/ingest_kb.py
```

## What good looks like

One topic per `##` section. Concrete and specific — the agent quotes these
almost verbatim, and it will say "no article covers that" and escalate rather
than fill a gap. That refusal is the feature: it is what stops invented policy.
