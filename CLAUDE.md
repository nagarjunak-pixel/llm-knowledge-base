# Agent Guide: Maintaining this Knowledge Base

You are the primary author and curator of `wiki/`. The human rarely edits it directly. Treat the wiki as a living, LLM-maintained artifact.

## Core rules

1. **Never discard user content in `raw/`.** It is the source of truth. Only read, never rewrite.
2. **All wiki edits are yours.** Keep markdown clean, use Obsidian-style `[[wikilinks]]`, and prefer short, focused articles over long monoliths.
3. **Every source in `raw/` should have exactly one summary file in `wiki/summaries/`** named after the source, with frontmatter:
   ```
   ---
   source: raw/articles/example.md
   added: YYYY-MM-DD
   tags: [topic1, topic2]
   ---
   ```
4. **Concept articles live in `wiki/concepts/`.** Each represents one idea, entity, method, or question. Link liberally to summaries and other concepts.
5. **Keep `wiki/index.md` current.** It should list concept articles grouped by theme and recent additions.
6. **Backlinks matter.** When you add a link `[[X]]` in article A, ensure X mentions A where relevant.

## Compile loop (when user says "update the wiki")

1. Run `python tools/ingest.py` to find unsummarized sources in `raw/`.
2. For each new source: read it, write a summary in `wiki/summaries/`, and either extend existing concept articles or create new ones.
3. Update `wiki/index.md` with new entries.
4. Run `python tools/lint.py` and fix any broken links or orphans you introduced.

## Query loop (when user asks a question)

1. Start from `wiki/index.md`, then follow links. Use `tools/search.py <query>` for keyword lookup.
2. If the wiki is insufficient, read from `raw/` directly.
3. Write the answer as a markdown file in `outputs/` with a timestamped name. For multi-part answers, consider Marp slides.
4. Suggest whether the answer (or parts of it) should be filed into `wiki/concepts/`.

## Lint loop (when user says "lint the wiki")

1. Run `python tools/lint.py`.
2. Flag inconsistencies, stale facts, missing citations, and orphan files.
3. Propose 3–5 candidate new concept articles based on recurring themes in summaries.
4. Write the report to `wiki/_meta/lint-YYYY-MM-DD.md`.

## Style

- Prefer bullet points and short paragraphs.
- Cite sources with relative links: `see [[summaries/example]]`.
- Use `> [!note]` callouts for your own uncertainty or open questions.
- Dates in ISO format.
