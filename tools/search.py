#!/usr/bin/env python3
"""Naive keyword search over the wiki. Usable from CLI or as an agent tool.

Usage: python tools/search.py <query> [--path wiki]
Prints matching files with the top-matching line for each.
"""
import argparse
import pathlib
import re
import sys


def search(root: pathlib.Path, query: str, max_results: int = 20):
    terms = [t.lower() for t in query.split() if t.strip()]
    if not terms:
        return []
    results = []
    for md in root.rglob("*.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lower = text.lower()
        score = sum(lower.count(t) for t in terms)
        if score == 0:
            continue
        snippet = ""
        for line in text.splitlines():
            if any(t in line.lower() for t in terms):
                snippet = line.strip()
                break
        results.append((score, md, snippet))
    results.sort(key=lambda r: -r[0])
    return results[:max_results]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("query", nargs="+")
    p.add_argument("--path", default="wiki")
    args = p.parse_args()
    root = pathlib.Path(args.path)
    if not root.exists():
        print(f"path not found: {root}", file=sys.stderr)
        sys.exit(1)
    hits = search(root, " ".join(args.query))
    if not hits:
        print("(no matches)")
        return
    for score, path, snippet in hits:
        print(f"{score:>4}  {path}")
        if snippet:
            print(f"       {snippet[:200]}")


if __name__ == "__main__":
    main()
