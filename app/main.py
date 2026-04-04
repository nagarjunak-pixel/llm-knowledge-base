"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

from .compile import compile_once, update_index
from .config import Settings, get_settings
from .db import Database
from .ingest import add_source, status as ingest_status
from .llm import LLMClient
from .query import answer
from .wiki import reindex, render_wikilinks, tree

logger = logging.getLogger("llm_kb")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="LLM Knowledge Base", version="0.1.0")

_md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True}).enable("table")


def get_db(settings: Settings = Depends(get_settings)) -> Database:
    return Database(settings.db_path)


def get_llm(settings: Settings = Depends(get_settings)) -> LLMClient:
    return LLMClient(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
    )


_templates_dir = Path(__file__).parent / "templates"
_static_dir = Path(__file__).parent / "static"
templates = Jinja2Templates(directory=str(_templates_dir))
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.on_event("startup")
def _startup() -> None:
    settings = get_settings()
    db = Database(settings.db_path)
    reindex(settings, db)
    update_index(settings, db)
    reindex(settings, db)
    logger.info("startup complete; llm_enabled=%s", settings.llm_enabled)


# ---- HTML routes ------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def home(request: Request, settings: Settings = Depends(get_settings),
         db: Database = Depends(get_db)):
    reindex(settings, db)
    index_md = (settings.wiki_dir / "index.md").read_text(encoding="utf-8") \
        if (settings.wiki_dir / "index.md").exists() else "# Wiki\n\n_empty_"
    html = _md.render(render_wikilinks(index_md, settings))
    st = ingest_status(settings)
    events = [dict(r) for r in db.recent_events(limit=10)]
    return templates.TemplateResponse("home.html", {
        "request": request,
        "settings": settings,
        "index_html": html,
        "status": st,
        "events": events,
        "llm_enabled": settings.llm_enabled,
    })


@app.get("/view/{rel_path:path}", response_class=HTMLResponse)
def view(rel_path: str, request: Request,
         settings: Settings = Depends(get_settings)):
    target = (settings.root_dir / rel_path).resolve()
    if not _within_managed(target, settings):
        raise HTTPException(status_code=400, detail="path not allowed")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="not found")
    if target.suffix.lower() in {".md", ".markdown", ".txt"}:
        raw = target.read_text(encoding="utf-8", errors="ignore")
        html = _md.render(render_wikilinks(raw, settings))
        return templates.TemplateResponse("view.html", {
            "request": request,
            "rel": rel_path,
            "title": target.stem,
            "content_html": html,
            "raw": raw,
        })
    # Non-text: send as download link.
    return templates.TemplateResponse("view.html", {
        "request": request,
        "rel": rel_path,
        "title": target.name,
        "content_html": f"<p>Binary file: <code>{rel_path}</code></p>",
        "raw": "",
    })


@app.get("/browse", response_class=HTMLResponse)
def browse(request: Request, settings: Settings = Depends(get_settings)):
    return templates.TemplateResponse("browse.html", {
        "request": request,
        "tree": tree(settings),
    })


@app.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = "",
           db: Database = Depends(get_db)):
    results = db.search(q) if q else []
    return templates.TemplateResponse("search.html", {
        "request": request,
        "q": q,
        "results": results,
    })


@app.get("/query", response_class=HTMLResponse)
def query_form(request: Request, settings: Settings = Depends(get_settings)):
    return templates.TemplateResponse("query.html", {
        "request": request,
        "llm_enabled": settings.llm_enabled,
        "result": None,
    })


@app.post("/query", response_class=HTMLResponse)
def query_submit(request: Request, question: str = Form(...),
                 settings: Settings = Depends(get_settings),
                 db: Database = Depends(get_db),
                 llm: LLMClient = Depends(get_llm)):
    result = answer(settings, db, llm, question)
    result["answer_html"] = _md.render(result["answer"])
    return templates.TemplateResponse("query.html", {
        "request": request,
        "llm_enabled": settings.llm_enabled,
        "result": result,
    })


@app.get("/ingest", response_class=HTMLResponse)
def ingest_view(request: Request, settings: Settings = Depends(get_settings)):
    return templates.TemplateResponse("ingest.html", {
        "request": request,
        "status": ingest_status(settings),
    })


@app.post("/ingest/upload")
def ingest_upload(file: UploadFile = File(...), category: str = Form("articles"),
                  settings: Settings = Depends(get_settings),
                  db: Database = Depends(get_db)):
    data = file.file.read()
    add_source(settings, db, relative_name=file.filename or "untitled",
               content=data, category=category)
    return RedirectResponse(url="/ingest", status_code=303)


@app.post("/compile")
def compile_action(settings: Settings = Depends(get_settings),
                   db: Database = Depends(get_db),
                   llm: LLMClient = Depends(get_llm)):
    report = compile_once(settings, db, llm)
    return JSONResponse(report)


# ---- JSON API ---------------------------------------------------------------


@app.get("/api/health")
def health(settings: Settings = Depends(get_settings)):
    return {"status": "ok", "version": "0.1.0", "llm_enabled": settings.llm_enabled}


@app.get("/api/status")
def api_status(settings: Settings = Depends(get_settings),
               db: Database = Depends(get_db)):
    st = ingest_status(settings)
    docs = db.list_documents()
    return {
        "llm_enabled": settings.llm_enabled,
        "sources_total": st.total_sources,
        "summaries_total": st.summarized,
        "pending": st.pending,
        "documents_indexed": len(docs),
    }


@app.get("/api/search")
def api_search(q: str, db: Database = Depends(get_db)):
    return {"query": q, "results": db.search(q)}


@app.post("/api/compile")
def api_compile(settings: Settings = Depends(get_settings),
                db: Database = Depends(get_db),
                llm: LLMClient = Depends(get_llm)):
    return compile_once(settings, db, llm)


@app.post("/api/query")
def api_query(payload: dict, settings: Settings = Depends(get_settings),
              db: Database = Depends(get_db),
              llm: LLMClient = Depends(get_llm)):
    question = (payload or {}).get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question required")
    return answer(settings, db, llm, question, save=bool(payload.get("save", True)))


# ---- helpers ---------------------------------------------------------------


def _within_managed(target: Path, settings: Settings) -> bool:
    for root in (settings.wiki_dir, settings.raw_dir, settings.outputs_dir):
        try:
            target.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False
