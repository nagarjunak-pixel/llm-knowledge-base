"""Compile loop: summarize pending sources with the LLM, update the wiki index."""
from __future__ import annotations

import time
from pathlib import Path

from .config import Settings
from .db import Database
from .ingest import list_sources, status as ingest_status, write_summary
from .llm import LLMClient
from .wiki import reindex

SYSTEM_SUMMARIZE = (
    "You are the curator of a personal knowledge base. Given a source document, "
    "produce a concise markdown summary with: a 3-sentence overview, 3-6 bullet "
    "key points, and 3-6 lowercase tag keywords. Be factual. Do not invent "
    "citations. Output only the markdown body (no frontmatter, no title)."
)


def _read_source(path: Path) -> str:
    if path.suffix.lower() in {".md", ".markdown", ".txt", ".html", ".htm", ".csv", ".json"}:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""
    return f"(binary file: {path.name})"


def _title_for(path: Path) -> str:
    return path.stem.replace("-", " ").replace("_", " ").strip().title() or path.name


def _extract_tags(body: str) -> list[str]:
    # Find a "Tags" line in the generated body and split it.
    for line in body.splitlines():
        low = line.lower().strip()
        if low.startswith("tags:") or low.startswith("## tags"):
            rest = line.split(":", 1)[-1] if ":" in line else ""
            return [t.strip().lstrip("#") for t in rest.split(",") if t.strip()]
    return []


def compile_once(settings: Settings, db: Database, llm: LLMClient,
                 limit: int | None = None) -> dict:
    """Summarize pending sources. Returns a dict report."""
    reindex(settings, db)
    st = ingest_status(settings)
    pending_rels = st.pending[: limit] if limit else st.pending
    written: list[str] = []
    errors: list[str] = []

    for rel in pending_rels:
        src_path = settings.root_dir / rel
        try:
            content = _read_source(src_path)
            user = (
                f"Source path: {rel}\n"
                f"Title hint: {_title_for(src_path)}\n"
                "---CONTENT---\n"
                f"{content[:16000]}"
            )
            resp = llm.complete(SYSTEM_SUMMARIZE, user)
            tags = _extract_tags(resp.text)
            out = write_summary(
                settings, db,
                source_rel=rel,
                title=_title_for(src_path),
                body=resp.text,
                tags=tags,
            )
            written.append(str(out.relative_to(settings.root_dir)))
        except Exception as exc:
            errors.append(f"{rel}: {exc}")

    update_index(settings, db)
    reindex(settings, db)
    db.log_event(
        "compile",
        f"wrote {len(written)} summaries, {len(errors)} errors",
        time.time(),
    )
    return {
        "processed": len(pending_rels),
        "written": written,
        "errors": errors,
        "llm_online": llm.online,
    }


def update_index(settings: Settings, db: Database) -> Path:
    """Regenerate wiki/index.md from the current state of the wiki."""
    wiki = settings.wiki_dir
    summaries = sorted((wiki / "summaries").glob("*.md")) if (wiki / "summaries").exists() else []
    concepts = sorted((wiki / "concepts").glob("*.md")) if (wiki / "concepts").exists() else []
    lines = ["# Wiki Index", "",
             "_Auto-maintained by the compile loop._", ""]
    lines.append("## Concepts")
    if concepts:
        for p in concepts:
            lines.append(f"- [[concepts/{p.stem}]]")
    else:
        lines.append("_No concept articles yet._")
    lines.append("")
    lines.append("## Recent summaries")
    if summaries:
        for p in sorted(summaries, key=lambda x: -x.stat().st_mtime)[:50]:
            lines.append(f"- [[summaries/{p.stem}]]")
    else:
        lines.append("_No summaries yet._")
    lines.append("")
    lines.append(f"_Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}_")
    out = wiki / "index.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    db.log_event("index", "rebuilt wiki/index.md", time.time())
    return out
