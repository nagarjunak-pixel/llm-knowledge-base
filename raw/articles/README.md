# LLM Knowledge Base

A personal knowledge base scaffold inspired by Karpathy's "LLM wiki" idea: raw sources are ingested, an LLM compiles them into a linked markdown wiki, and the wiki is queried, visualized, and improved by LLM agents. Obsidian is the recommended frontend.

## Layout

```
raw/          # Source documents: articles, papers, images, datasets
  articles/   # Web clippings (.md via Obsidian Web Clipper)
  papers/     # PDFs and paper notes
  images/     # Figures, screenshots
  data/       # CSVs, JSON, etc.
wiki/         # LLM-maintained knowledge base (markdown)
  index.md    # Top-level index, auto-maintained
  concepts/   # Concept articles (one topic per file)
  summaries/  # Per-source summaries with backlinks
  _meta/      # Health checks, TODOs, open questions
outputs/      # Generated artifacts: slides, plots, reports
tools/        # Helper CLIs (search, lint, ingest)
```

## Workflow

1. **Ingest** — drop sources into `raw/`. Use Obsidian Web Clipper for web articles.
2. **Compile** — ask the agent to update the wiki: summarize new sources, create/update concept articles, add backlinks.
3. **Query** — ask complex questions; the agent reads `wiki/index.md` and follows links. Outputs go to `outputs/` as `.md`, Marp slides, or plots.
4. **File back** — promote useful outputs into the wiki.
5. **Lint** — run health checks to find inconsistencies, missing data, and new article candidates.

## Agent instructions

See `CLAUDE.md` for the rules the agent follows when maintaining this knowledge base.

## Tools

- `tools/search.py` — naive grep-based search over the wiki, usable from CLI or as an agent tool.
- `tools/ingest.py` — list new files in `raw/` that are not yet summarized in `wiki/summaries/`.
- `tools/lint.py` — report broken wiki links and orphan articles.

## Viewing

Open the repo root as an Obsidian vault. Install the Marp plugin to render slide outputs.
