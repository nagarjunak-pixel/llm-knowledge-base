import io


def test_health(client):
    c, _ = client
    r = c.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["llm_enabled"] is False


def test_home_renders(client):
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200
    assert "Wiki index" in r.text


def test_upload_and_compile_and_query(client):
    c, settings = client
    # Upload a raw source.
    files = {"file": ("attention.md",
                      b"# Attention\n\nAttention is all you need. Transformers rely on self-attention.",
                      "text/markdown")}
    r = c.post("/ingest/upload", files=files, data={"category": "articles"})
    assert r.status_code in (200, 303)

    # Trigger compile.
    r = c.post("/compile")
    assert r.status_code == 200
    report = r.json()
    assert report["processed"] >= 1
    assert (settings.wiki_dir / "summaries" / "attention.md").exists()

    # Search should find the summary.
    r = c.get("/api/search", params={"q": "attention"})
    assert r.status_code == 200
    results = r.json()["results"]
    assert any("attention" in h["path"].lower() for h in results)

    # Query endpoint.
    r = c.post("/api/query", json={"question": "what is attention?"})
    assert r.status_code == 200
    data = r.json()
    assert data["answer"]
    assert data["output"]


def test_view_endpoint(client):
    c, settings = client
    (settings.wiki_dir / "concepts").mkdir(parents=True, exist_ok=True)
    (settings.wiki_dir / "concepts" / "test.md").write_text("# Test\n\nHello.", encoding="utf-8")
    r = c.get("/view/wiki/concepts/test.md")
    assert r.status_code == 200
    assert "Hello" in r.text


def test_view_rejects_escape(client):
    c, _ = client
    r = c.get("/view/../../etc/passwd")
    assert r.status_code in (400, 404)
