#!/usr/bin/env python3
"""Report broken wikilinks and orphan articles in wiki/."""
import pathlib
import re

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


def main():
    wiki = pathlib.Path("wiki")
    if not wiki.exists():
        print("wiki/ not found")
        return

    files = list(wiki.rglob("*.md"))
    stems = {p.stem: p for p in files}
    stems_lower = {k.lower(): v for k, v in stems.items()}

    broken = []
    referenced = set()
    for md in files:
        text = md.read_text(encoding="utf-8", errors="ignore")
        for m in WIKILINK.finditer(text):
            target = m.group(1).strip().split("/")[-1]
            key = target.lower()
            if key in stems_lower:
                referenced.add(stems_lower[key].stem)
            else:
                broken.append((md, target))

    orphans = [p for stem, p in stems.items()
               if stem not in referenced and p.name != "index.md"]

    print(f"files: {len(files)}")
    print(f"broken links: {len(broken)}")
    for md, target in broken:
        print(f"  {md} -> [[{target}]]")
    print(f"orphans (not linked from anywhere): {len(orphans)}")
    for p in orphans:
        print(f"  {p}")


if __name__ == "__main__":
    main()
