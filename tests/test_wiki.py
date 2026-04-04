from pathlib import Path

from app.wiki import reindex, render_wikilinks, resolve_wikilink


def test_reindex_picks_up_files(kb):
    settings, db, _ = kb
    (settings.wiki_dir / "concepts").mkdir(parents=True, exist_ok=True)
    (settings.wiki_dir / "concepts" / "alpha.md").write_text("# Alpha\n\nHello world.", encoding="utf-8")
    (settings.raw_dir / "articles" / "foo.md").write_text("raw source about alpha", encoding="utf-8")

    count = reindex(settings, db)
    assert count >= 2
    paths = {row["path"] for row in db.list_documents()}
    assert any("alpha.md" in p for p in paths)
    assert any("foo.md" in p for p in paths)


def test_wikilink_resolution(kb):
    settings, _, _ = kb
    concepts = settings.wiki_dir / "concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    (concepts / "beta.md").write_text("# Beta\n", encoding="utf-8")

    resolved = resolve_wikilink("beta", settings)
    assert resolved is not None
    assert resolved.name == "beta.md"

    rendered = render_wikilinks("see [[beta]] and [[missing]]", settings)
    assert "/view/wiki/concepts/beta.md" in rendered
    assert "broken-link" in rendered


def test_fts_search(kb):
    settings, db, _ = kb
    concepts = settings.wiki_dir / "concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    (concepts / "llm.md").write_text("# LLM\n\nLarge language models are neural networks.", encoding="utf-8")
    reindex(settings, db)
    hits = db.search("neural")
    assert hits, "expected FTS hit for 'neural'"
    assert any("llm.md" in h["path"] for h in hits)
