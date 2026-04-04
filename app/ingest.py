"""Ingest logic: discover raw/ sources, diff against existing summaries."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .db import Database
from .wiki import read_doc, reindex, safe_write

SOURCE_EXTS = {".md", ".markdown", ".txt", ".pdf", ".csv", ".json",
               ".png", ".jpg", ".jpeg", ".html", ".htm"}
FRONTMATTER_SOURCE_RE = re.compile(r"^source:\s*(.+)$", re.MULTILINE)


@dataclass
class IngestStatus:
    total_sources: int
    summarized: int
    pending: list[str]


def list_sources(settings: Settings) -> list[Path]:
    if not settings.raw_dir.exists():
        return []
    return [
        p for p in sorted(settings.raw_dir.rglob("*"))
        if p.is_file()
        and p.suffix.lower() in SOURCE_EXTS
        and not p.name.startswith(".")
    ]


def summarized_sources(settings: Settings) -> set[str]:
    summaries_dir = settings.wiki_dir / "summaries"
    seen: set[str] = set()
    if not summaries_dir.exists():
        return seen
    for md in summaries_dir.rglob("*.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in FRONTMATTER_SOURCE_RE.finditer(text):
            seen.add(m.group(1).strip())
    return seen


def status(settings: Settings) -> IngestStatus:
    sources = list_sources(settings)
    summarized = summarized_sources(settings)
    rels = [str(p.relative_to(settings.root_dir)) for p in sources]
    pending = [r for r in rels if r not in summarized]
    return IngestStatus(total_sources=len(sources), summarized=len(summarized),
                        pending=pending)


def add_source(settings: Settings, db: Database, *, relative_name: str,
               content: bytes, category: str = "articles") -> Path:
    """Store an uploaded file under raw/<category>/. Reindexes on success."""
    category = category.strip().strip("/") or "articles"
    safe_name = Path(relative_name).name or "untitled"
    target = settings.raw_dir / category / safe_name
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        i = 2
        while True:
            candidate = target.with_name(f"{stem}-{i}{suffix}")
            if not candidate.exists():
                target = candidate
                break
            i += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    db.log_event("ingest", f"added {target.relative_to(settings.root_dir)}", time.time())
    reindex(settings, db)
    return target


def write_summary(settings: Settings, db: Database, *, source_rel: str,
                  title: str, body: str, tags: list[str]) -> Path:
    summaries_dir = settings.wiki_dir / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(source_rel).stem
    out = summaries_dir / f"{stem}.md"
    today = time.strftime("%Y-%m-%d")
    tag_str = ", ".join(tags) if tags else ""
    content = (
        f"---\n"
        f"source: {source_rel}\n"
        f"added: {today}\n"
        f"tags: [{tag_str}]\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{body}\n"
    )
    safe_write(out, content, settings)
    db.log_event("summary", f"wrote {out.relative_to(settings.root_dir)}", time.time())
    return out
