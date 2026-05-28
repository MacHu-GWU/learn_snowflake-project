---
name: snowflake-docs
description: Authoritative Snowflake documentation lookup. Use whenever the user asks about Snowflake SQL syntax, Cortex AI / ML functions, Snowpark, Dynamic Tables, Iceberg Tables, Streamlit in Snowflake, Snowpark Container Services, Snowflake CLI, REST API, connectors/drivers, Account/Organization Usage views, Information Schema, migrations, or any other Snowflake feature where you need a current authoritative reference instead of relying on training-data memory. Navigate the official Snowflake docs catalog with WebFetch.
allowed-tools: WebFetch
---

# Snowflake docs — 3-tier live navigation

Snowflake publishes an LLM-friendly doc catalog at
<https://docs.snowflake.com/llms.txt>. It is organized in **three tiers**:

```
Level 1   https://docs.snowflake.com/llms.txt
              Top-level table of contents — sections + entries.

Level 2   The links found in Level 1:
              - <…>.md          topic landing page (overview + hrefs to detail pages)
              - <…>/llms.txt    section page index (flat list of detail-page URLs)

Level 3   Actual doc content pages (.md). Reached from hrefs/links inside
          a Level-2 file.
```

Nothing is cached. Every page is fetched live with `WebFetch`. This keeps
you on whatever Snowflake publishes right now — which matters because
Snowflake's own LLM guidance says SQL syntax evolves frequently and you
should **always** prefer the live docs over memorized syntax (especially
for **Cortex AI**, **Dynamic Tables**, and **Iceberg Tables**). For
Snowpark Python, verify method signatures against the versioned reference.
Use the `<orgname>-<accountname>` identifier format in new code.

## How to look something up

1. **`WebFetch` <https://docs.snowflake.com/llms.txt>.** This is the
   Level-1 TOC: section headers (`## Snowflake Cortex (AI & ML)`,
   `## SQL Commands`, `## Snowpark`, `## Account Usage`, etc.) followed by
   `- [Title](URL)` entries. Scan it for the entry whose title best
   matches the user's question. That entry's URL is your Level-2 target.
   When `WebFetch`-ing, you can pass a focused `prompt` (e.g. "list every
   entry under SQL Functions related to JSON") to get just the section
   you need instead of the whole TOC.

2. **`WebFetch` the Level-2 URL exactly as listed.**
   - If the URL ends in `.md`, you get a topic landing page: short
     overview plus markdown links of the form `[Title](/relative/path)`
     pointing to Level-3 detail pages.
   - If the URL ends in `/llms.txt`, you get a flat section index:
     `- [Title](full URL)` entries pointing directly to Level-3 `.md`
     pages.

3. **Decide whether Level 2 already answers the question.** For "which
   view tracks X" or "what's the signature of Y", the landing page or the
   one-line entry titles in the index are often enough. If not, go to
   Level 3.

4. **`WebFetch` the Level-3 page.** Construct the URL:

   - **From a `.llms.txt` index entry**: the URL is already a full
     `https://docs.snowflake.com/en/…/<page>.md`. Use it as-is.
   - **From a relative href inside a `.md` topic page**: the href looks
     like `/user-guide/alerts` (no extension). Prepend
     `https://docs.snowflake.com/en` and append `.md`:
     - `/user-guide/alerts` → `https://docs.snowflake.com/en/user-guide/alerts.md`
     - `/sql-reference/functions/array_agg` →
       `https://docs.snowflake.com/en/sql-reference/functions/array_agg.md`

   The `.md` suffix is what returns the LLM-friendly markdown variant —
   without it you get the HTML page, which is much noisier.

5. **Iterate as needed.** A topic page sometimes points to another
   landing page (which then points to the real detail page). Keep
   resolving hrefs the same way until you reach a content page that
   answers the question.

6. **If no Level-1 title matches the user's term**, pick the most
   plausible section and `WebFetch` its Level-2 file anyway — Level-2
   files contain keyword-rich titles for every Level-3 page in that area
   and a quick scan usually surfaces the right link.

## Guardrails when answering

- If a question maps to one of these docs, **always** fetch at least the
  Level-2 page before answering — don't rely on memorized syntax.
- When docs disagree with prior knowledge, the docs win; flag the
  discrepancy so the user can spot stale tutorials elsewhere.
- For Cortex / Dynamic Tables / Iceberg Tables, treat the docs as the
  source of truth even if they contradict older blog posts.
- Cite the upstream URL you fetched so the user can open it directly.
- `WebFetch` returns markdown; pass a specific question via the `prompt`
  argument to extract just the relevant section instead of pulling the
  whole page into context.
