from app.compile import compile_once, update_index
from app.ingest import add_source, status as ingest_status
from app.query import answer
from app.wiki import reindex


def test_compile_creates_summary(kb):
    settings, db, llm = kb
    add_source(settings, db,
               relative_name="rag.md",
               content=b"# RAG\n\nRetrieval augmented generation retrieves context "
                       b"from a vector store to ground LLM answers.",
               category="articles")
    report = compile_once(settings, db, llm)
    assert report["processed"] >= 1
    assert report["llm_online"] is False  # offline fallback in tests
    assert (settings.wiki_dir / "summaries" / "rag.md").exists()

    # Status should now show zero pending.
    st = ingest_status(settings)
    assert st.total_sources >= 1
    assert not st.pending


def test_update_index_lists_concepts(kb):
    settings, db, _ = kb
    (settings.wiki_dir / "concepts").mkdir(parents=True, exist_ok=True)
    (settings.wiki_dir / "concepts" / "gamma.md").write_text("# Gamma", encoding="utf-8")
    update_index(settings, db)
    content = (settings.wiki_dir / "index.md").read_text(encoding="utf-8")
    assert "gamma" in content.lower()


def test_query_answer(kb):
    settings, db, llm = kb
    (settings.wiki_dir / "concepts").mkdir(parents=True, exist_ok=True)
    (settings.wiki_dir / "concepts" / "rlhf.md").write_text(
        "# RLHF\n\nReinforcement learning from human feedback aligns models with human preferences.",
        encoding="utf-8",
    )
    reindex(settings, db)
    result = answer(settings, db, llm, "what is rlhf?")
    assert result["question"] == "what is rlhf?"
    assert result["answer"]
    assert result["output"]
    saved = settings.root_dir / result["output"]
    assert saved.exists()
