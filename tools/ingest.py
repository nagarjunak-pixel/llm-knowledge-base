#!/usr/bin/env python3
"""List sources in raw/ that do not yet have a summary in wiki/summaries/.

A source is considered summarized if any file in wiki/summaries/ contains
`source: <relative-path>` in its frontmatter.
"""
import pathlib
import re


def collect_sources(raw: pathlib.Path):
    exts = {".md", ".pdf", ".txt", ".csv", ".json", ".png", ".jpg", ".jpeg"}
    return [p for p in raw.rglob("*") if p.is_file() and p.suffix.lower() in exts]


def collect_summarized(summaries: pathlib.Path):
    seen = set()
    pat = re.compile(r"^source:\s*(.+)$", re.MULTILINE)
    for md in summaries.rglob("*.md"):
        text = md.read_text(encoding="utf-8", errors="ignore")
        for m in pat.finditer(text):
            seen.add(m.group(1).strip())
    return seen


def main():
    root = pathlib.Path(".")
    raw = root / "raw"
    summaries = root / "wiki" / "summaries"
    if not raw.exists():
        print("raw/ not found")
        return
    sources = collect_sources(raw)
    summarized = collect_summarized(summaries) if summaries.exists() else set()
    pending = [p for p in sources if str(p) not in summarized]
    print(f"{len(sources)} sources, {len(summarized)} summarized, {len(pending)} pending")
    for p in pending:
        print(f"  {p}")


if __name__ == "__main__":
    main()
