"""Wiki filesystem operations: read, write, index, link resolution."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import Settings
from .db import Database

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

TEXT_EXTS = {".md", ".markdown", ".txt"}


@dataclass
class Document:
    path: Path
    rel: str
    kind: str
    title: str
    body: str
    mtime: float
    size: int


def _kind_for(path: Path, settings: Settings) -> str:
    try:
        path.relative_to(settings.wiki_dir)
        return "wiki"
    except ValueError:
        pass
    try:
        path.relative_to(settings.outputs_dir)
        return "output"
    except ValueError:
        pass
    return "raw"


def title_from_body(path: Path, body: str) -> str:
    m = TITLE_RE.search(body)
    if m:
        return m.group(1).strip()
    return path.stem.replace("_", " ").replace("-", " ").title()


def read_doc(path: Path, settings: Settings) -> Document:
    body = ""
    if path.suffix.lower() in TEXT_EXTS:
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            body = ""
    stat = path.stat()
    rel = str(path.relative_to(settings.root_dir))
    return Document(
        path=path,
        rel=rel,
        kind=_kind_for(path, settings),
        title=title_from_body(path, body) if body else path.name,
        body=body,
        mtime=stat.st_mtime,
        size=stat.st_size,
    )


def walk_tracked(settings: Settings) -> Iterable[Path]:
    roots = [settings.wiki_dir, settings.raw_dir, settings.outputs_dir]
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.name.startswith("."):
                continue
            yield p


def reindex(settings: Settings, db: Database) -> int:
    """Rebuild the SQLite index from the filesystem. Returns doc count."""
    existing = {row["path"] for row in db.list_documents()}
    seen: set[str] = set()
    count = 0
    for p in walk_tracked(settings):
        doc = read_doc(p, settings)
        db.upsert_document(
            path=doc.rel,
            kind=doc.kind,
            title=doc.title,
            body=doc.body,
            mtime=doc.mtime,
            size=doc.size,
        )
        seen.add(doc.rel)
        count += 1
    for stale in existing - seen:
        db.delete_document(stale)
    db.log_event("reindex", f"indexed {count} documents", time.time())
    return count


def resolve_wikilink(target: str, settings: Settings) -> Path | None:
    """Resolve a [[wikilink]] target to a file inside wiki/. Case-insensitive stem."""
    target = target.strip()
    if not target:
        return None
    # Allow "folder/name" style targets.
    candidate = settings.wiki_dir / (target + ".md")
    if candidate.exists():
        return candidate
    target_stem = Path(target).name.lower()
    for md in settings.wiki_dir.rglob("*.md"):
        if md.stem.lower() == target_stem:
            return md
    return None


def render_wikilinks(body: str, settings: Settings) -> str:
    """Replace [[X]] with regular markdown links where the target exists."""
    def repl(m: re.Match[str]) -> str:
        target = m.group(1).strip()
        alias = (m.group(2) or target).strip()
        resolved = resolve_wikilink(target, settings)
        if resolved is None:
            return f"<span class=\"broken-link\">[[{alias}]]</span>"
        rel = resolved.relative_to(settings.root_dir)
        return f"[{alias}](/view/{rel.as_posix()})"

    return WIKILINK_RE.sub(repl, body)


def safe_write(path: Path, content: str, settings: Settings) -> Path:
    """Write text content to a path, ensuring it lives under a managed dir."""
    allowed_roots = [settings.wiki_dir, settings.outputs_dir, settings.raw_dir]
    target = path.resolve()
    if not any(_is_within(target, root) for root in allowed_roots):
        raise ValueError(f"refusing to write outside managed dirs: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def tree(settings: Settings) -> dict:
    """Return a nested dict describing the wiki/raw/outputs tree for the UI."""
    def node_for(root: Path) -> dict:
        entries: list[dict] = []
        if root.exists():
            for p in sorted(root.rglob("*")):
                if p.name.startswith(".") or not p.is_file():
                    continue
                entries.append({
                    "rel": p.relative_to(settings.root_dir).as_posix(),
                    "name": p.name,
                    "parent": p.parent.relative_to(root).as_posix(),
                })
        return {"root": root.name, "files": entries}

    return {
        "wiki": node_for(settings.wiki_dir),
        "raw": node_for(settings.raw_dir),
        "outputs": node_for(settings.outputs_dir),
    }
