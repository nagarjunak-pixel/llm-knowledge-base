"""Query loop: answer questions against the wiki with the LLM + FTS retrieval."""
from __future__ import annotations

import time
from pathlib import Path

from .config import Settings
from .db import Database
from .llm import LLMClient

SYSTEM_QUERY = (
    "You are an expert assistant answering questions against a user's personal "
    "markdown knowledge base. You will be given the question and a bundle of "
    "retrieved passages from the wiki. Ground your answer in the passages, cite "
    "sources inline using relative paths in square brackets like [wiki/concepts/x.md], "
    "and clearly note when the wiki does not contain enough information."
)


def _gather_context(db: Database, settings: Settings, question: str,
                    max_docs: int = 8, max_chars_per_doc: int = 1500) -> list[dict]:
    hits = db.search(question, limit=max_docs)
    context: list[dict] = []
    for hit in hits:
        path = settings.root_dir / hit["path"]
        body = ""
        if path.exists() and path.suffix.lower() in {".md", ".txt", ".markdown"}:
            try:
                body = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                body = ""
        context.append({
            "path": hit["path"],
            "title": hit["title"],
            "snippet": hit.get("snippet", ""),
            "body": body[:max_chars_per_doc],
        })
    return context


def answer(settings: Settings, db: Database, llm: LLMClient, question: str,
           save: bool = True) -> dict:
    ctx = _gather_context(db, settings, question)
    context_blob = "\n\n".join(
        f"### Source: {c['path']}\n{c['body'] or c['snippet']}" for c in ctx
    )
    user = (
        f"Question: {question}\n\n"
        f"Retrieved passages:\n{context_blob if context_blob else '(none found)'}"
    )
    resp = llm.complete(SYSTEM_QUERY, user)

    output_path: Path | None = None
    if save:
        ts = time.strftime("%Y%m%d-%H%M%S")
        slug = "".join(c if c.isalnum() else "-" for c in question.lower())[:60].strip("-")
        output_path = settings.outputs_dir / f"{ts}-{slug or 'query'}.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sources_md = "\n".join(f"- [{c['path']}](/view/{c['path']})" for c in ctx) or "- (none)"
        output_path.write_text(
            f"# Query: {question}\n\n"
            f"_Answered at {time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"by {resp.model}{' (offline)' if resp.offline else ''}._\n\n"
            f"{resp.text}\n\n"
            f"## Sources consulted\n{sources_md}\n",
            encoding="utf-8",
        )
        db.log_event("query", f"saved answer to {output_path.relative_to(settings.root_dir)}",
                     time.time())

    return {
        "question": question,
        "answer": resp.text,
        "model": resp.model,
        "offline": resp.offline,
        "sources": [c["path"] for c in ctx],
        "output": str(output_path.relative_to(settings.root_dir)) if output_path else None,
    }
