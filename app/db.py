"""SQLite storage with FTS5 for full-text search over the wiki."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL,           -- 'wiki' | 'raw' | 'output'
    title TEXT,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    path, title, body, kind
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    message TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ---- documents ---------------------------------------------------------

    def upsert_document(self, *, path: str, kind: str, title: str,
                        body: str, mtime: float, size: int) -> None:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT id FROM documents WHERE path = ?", (path,)
            )
            row = cur.fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO documents(path, kind, title, mtime, size) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (path, kind, title, mtime, size),
                )
                conn.execute(
                    "INSERT INTO documents_fts(path, title, body, kind) "
                    "VALUES (?, ?, ?, ?)",
                    (path, title, body, kind),
                )
            else:
                conn.execute(
                    "UPDATE documents SET kind=?, title=?, mtime=?, size=? WHERE path=?",
                    (kind, title, mtime, size, path),
                )
                conn.execute(
                    "DELETE FROM documents_fts WHERE path=?", (path,)
                )
                conn.execute(
                    "INSERT INTO documents_fts(path, title, body, kind) "
                    "VALUES (?, ?, ?, ?)",
                    (path, title, body, kind),
                )
            conn.commit()

    def delete_document(self, path: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM documents WHERE path=?", (path,))
            conn.execute("DELETE FROM documents_fts WHERE path=?", (path,))
            conn.commit()

    def list_documents(self, kind: str | None = None) -> list[sqlite3.Row]:
        with self.connect() as conn:
            if kind:
                cur = conn.execute(
                    "SELECT * FROM documents WHERE kind=? ORDER BY mtime DESC",
                    (kind,),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM documents ORDER BY mtime DESC"
                )
            return cur.fetchall()

    def search(self, query: str, limit: int = 25) -> list[dict]:
        if not query.strip():
            return []
        # Basic sanitization: FTS5 requires quoting of special chars.
        safe = query.replace('"', '""')
        fts_query = f'"{safe}"'
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT path, title, kind,
                       snippet(documents_fts, 2, '<mark>', '</mark>', '…', 12) AS snippet,
                       bm25(documents_fts) AS rank
                FROM documents_fts
                WHERE documents_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, limit),
            )
            return [dict(r) for r in cur.fetchall()]

    # ---- events ------------------------------------------------------------

    def log_event(self, kind: str, message: str, ts: float) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO events(ts, kind, message) VALUES (?, ?, ?)",
                (ts, kind, message),
            )
            conn.commit()

    def recent_events(self, limit: int = 50) -> list[sqlite3.Row]:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,)
            )
            return cur.fetchall()
