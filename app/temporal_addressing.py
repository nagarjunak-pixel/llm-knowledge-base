"""
Bi-temporal subject-keyed memory addressing (TASK Memory, arXiv:2611.34762),
cross-page table/footnote seam stitching (DocSEAM, arXiv:2611.34420), and
planted-citation trap verification for enterprise RAG & wiki synthesis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CLAUSE_TAG_RE = re.compile(r"\[([A-Za-z0-9_.:-]+)\]")


@dataclass(frozen=True)
class VersionedClause:
    clause_id: str
    subject_key: str
    text: str
    valid_from: str
    valid_to: str | None = None
    superseded_by: str | None = None

    def is_active_at(self, query_date: str) -> bool:
        if self.superseded_by is not None and self.valid_to is not None and query_date >= self.valid_to:
            return False
        if query_date < self.valid_from:
            return False
        if self.valid_to is not None and query_date >= self.valid_to:
            return False
        return True


class SubjectTemporalIndex:
    """Deterministically resolves active vs superseded clauses by (subject_key, query_date)."""

    def __init__(self) -> None:
        self._by_subject: dict[str, list[VersionedClause]] = {}
        self._by_id: dict[str, VersionedClause] = {}

    def upsert(self, clause: VersionedClause) -> None:
        self._by_id[clause.clause_id] = clause
        bucket = self._by_subject.setdefault(clause.subject_key, [])
        bucket[:] = [c for c in bucket if c.clause_id != clause.clause_id] + [clause]
        bucket.sort(key=lambda c: (c.valid_from, c.clause_id))

    def resolve_active(self, subject_key: str, query_date: str) -> list[VersionedClause]:
        clauses = self._by_subject.get(subject_key, [])
        return [c for c in clauses if c.is_active_at(query_date)]

    def format_addressed_context(self, subject_key: str, query_date: str) -> str:
        clauses = self._by_subject.get(subject_key, [])
        lines: list[str] = []
        for c in clauses:
            status = "ACTIVE" if c.is_active_at(query_date) else f"SUPERSEDED_BY:{c.superseded_by or 'EXPIRED'}"
            lines.append(f"[{c.clause_id}] ({c.subject_key} | {status} | from={c.valid_from}): {c.text}")
        return "\n".join(lines)

    def verify_citations(self, answer_text: str, query_date: str) -> tuple[bool, list[str]]:
        """Rejects fabricated clause IDs (citation traps) and citations to superseded clauses."""
        cited = sorted(set(CLAUSE_TAG_RE.findall(answer_text)))
        violations: list[str] = []
        for cid in cited:
            clause = self._by_id.get(cid)
            if clause is None:
                violations.append(f"unknown_citation_trap:{cid}")
            elif not clause.is_active_at(query_date):
                violations.append(f"superseded_clause_cited:{cid}")
        return len(violations) == 0, violations


def stitch_cross_page_seams(pages: list[str], seam_lines: int = 3) -> list[str]:
    """
    Zero-extra-vision-token page-boundary stitcher (DocSEAM pattern).
    Propagates markdown table headers and split trailing rows across page breaks.
    """
    if len(pages) <= 1:
        return list(pages)

    stitched: list[str] = [pages[0]]
    for idx in range(1, len(pages)):
        prev_lines = [ln for ln in pages[idx - 1].splitlines() if ln.strip()]
        curr_lines = pages[idx].splitlines()
        first_non_empty = next((ln.strip() for ln in curr_lines if ln.strip()), "")

        # Detect split Markdown table continuing on next page without its header row
        table_headers = [ln for ln in prev_lines if ln.strip().startswith("|")]
        if (
            first_non_empty.startswith("|")
            and len(table_headers) >= 2
            and not any(set(ln.strip()) <= set("|-: ") for ln in curr_lines[:3] if ln.strip())
        ):
            header_pair = "\n".join(table_headers[:2])
            stitched.append(f"{header_pair}\n{pages[idx]}")
        else:
            tail_context = "\n".join(prev_lines[-seam_lines:])
            stitched.append(f"<!-- seam_context: {tail_context} -->\n{pages[idx]}")
    return stitched
