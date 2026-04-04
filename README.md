# LLM Knowledge Base

A full, deployable web application that turns a directory of raw sources into an LLM-maintained markdown wiki you can browse, search, and query. Inspired by Karpathy's "LLM wiki" idea.

- **Ingest** any file (articles, notes, papers, data) via web upload or by dropping it into `raw/`.
- **Compile** — Claude reads each new source and writes a summary into `wiki/summaries/`, then rebuilds `wiki/index.md`.
- **Browse** the wiki with Obsidian-style `[[wikilinks]]` resolved to clickable links.
- **Search** with SQLite FTS5 (snippets with `<mark>` highlighting).
- **Ask** natural-language questions — the app retrieves relevant passages, asks Claude, and saves the answer into `outputs/` with source citations.
- **Offline-safe** — if no API key is set, a deterministic rule-based fallback keeps every endpoint working (useful for tests and demos).

## Stack

- Python 3.11 · FastAPI · Jinja2 · SQLite (FTS5) · anthropic SDK · markdown-it-py
- Zero JS build step: plain HTML + CSS, dark theme, mobile-friendly.
- 11 pytest tests covering the wiki engine, compile/query loops, and HTTP API.

## Layout

```
app/                FastAPI application
  main.py           routes (HTML + JSON)
  config.py         env-driven settings
  db.py             SQLite + FTS5
  wiki.py           wiki fs ops, wikilink resolver, indexer
  ingest.py         raw source discovery + uploads
  compile.py        LLM summarize loop + index rebuild
  query.py          retrieval + LLM answer + output save
  llm.py            anthropic client with offline fallback
  templates/        Jinja2 templates
  static/style.css  dark theme
raw/                your source documents (mounted volume in Docker)
wiki/               LLM-maintained markdown (mounted volume)
outputs/            generated answers / reports (mounted volume)
tools/              standalone CLIs (search.py, ingest.py, lint.py)
tests/              pytest suite
Dockerfile          production image
docker-compose.yml  one-command deploy with persistent volumes
```

## Quick start (local)

```bash
pip install -r requirements.txt
cp .env.example .env     # edit and paste your ANTHROPIC_API_KEY
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. Upload a markdown/txt file on the Ingest page, hit "Compile", and watch it appear in the wiki index.

## Production deploy (Docker)

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
docker compose up -d --build
```

The compose file mounts `raw/`, `wiki/`, and `outputs/` as host volumes so your data survives rebuilds, and keeps the SQLite index on a named volume (`kb-db`). Healthcheck hits `/api/health` every 30s.

Deploy anywhere Docker runs: a VPS (`docker compose up -d` behind nginx/caddy), Fly.io, Render, Railway, Google Cloud Run, AWS ECS, etc. Set `ANTHROPIC_API_KEY` as a secret in the target environment.

### Fly.io (one-command-ish)

A pre-configured `fly.toml` ships in the repo with a persistent volume for `raw/`, `wiki/`, `outputs/`, and the SQLite index.

```bash
# 1. Install flyctl and log in (once)
curl -L https://fly.io/install.sh | sh    # or: brew install flyctl
fly auth login

# 2. Launch — reuses the bundled fly.toml, no prompts for Dockerfile
fly launch --no-deploy --copy-config --name <your-app-name>

# 3. Create a 3 GB persistent volume in the same region
fly volumes create kb_data --region iad --size 3

# 4. Secrets
fly secrets set ANTHROPIC_API_KEY=sk-ant-...

# 5. Deploy
fly deploy
```

Fly prints the public URL (e.g. `https://your-app-name.fly.dev`). Change `iad` to the region nearest you (`lhr`, `fra`, `sin`, `syd`, `nrt`, ...).

### Recommended reverse proxy (Caddy)

```caddy
kb.example.com {
  reverse_proxy localhost:8000
}
```

TLS is handled automatically by Caddy. For nginx use a standard proxy_pass to `http://127.0.0.1:8000` and set `X-Forwarded-Proto` / `X-Forwarded-For` (uvicorn is launched with `--proxy-headers`).

## HTTP API

| Method | Path                  | Description                                    |
|--------|-----------------------|------------------------------------------------|
| GET    | `/api/health`         | liveness + LLM online status                   |
| GET    | `/api/status`         | counts: sources, summaries, pending, indexed   |
| GET    | `/api/search?q=...`   | FTS5 search over the wiki + raw + outputs      |
| POST   | `/api/compile`        | summarize pending sources, rebuild index       |
| POST   | `/api/query`          | `{question, save?}` → answer + sources + file  |
| POST   | `/ingest/upload`      | multipart upload, stored under `raw/<category>/` |

Example:

```bash
curl -X POST http://localhost:8000/api/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"summarize everything I know about RLHF"}'
```

## Testing

```bash
python -m pytest -q
```

The suite creates isolated tmp knowledge bases per test, uses the offline LLM stub, and exercises every route.

## Environment variables

| Var                    | Default             | Purpose                          |
|------------------------|---------------------|----------------------------------|
| `ANTHROPIC_API_KEY`    | _(unset)_           | Enables real Claude calls        |
| `ANTHROPIC_MODEL`      | `claude-opus-4-6`   | Model id                         |
| `ANTHROPIC_MAX_TOKENS` | `4096`              | Max tokens per response          |
| `PORT`                 | `8000`              | HTTP port                        |
| `LOG_LEVEL`            | `info`              | uvicorn log level                |

## Agent instructions

`CLAUDE.md` documents the compile / query / lint loops an LLM agent should follow when maintaining this knowledge base by hand (outside the web UI).
