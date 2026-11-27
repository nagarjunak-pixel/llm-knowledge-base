from app.temporal_addressing import (
    SubjectTemporalIndex,
    VersionedClause,
    stitch_cross_page_seams,
)


def test_bitemporal_resolution_and_citation_trap_refusal() -> None:
    idx = SubjectTemporalIndex()
    idx.upsert(
        VersionedClause(
            clause_id="POL-RET-2024",
            subject_key="data_retention",
            text="Audit logs are retained for 90 days.",
            valid_from="2024-01-01",
            valid_to="2026-01-01",
            superseded_by="POL-RET-2026",
        )
    )
    idx.upsert(
        VersionedClause(
            clause_id="POL-RET-2026",
            subject_key="data_retention",
            text="Audit logs are retained for 365 days.",
            valid_from="2026-01-01",
        )
    )

    active_2025 = idx.resolve_active("data_retention", "2025-06-15")
    assert [c.clause_id for c in active_2025] == ["POL-RET-2024"]

    active_2026 = idx.resolve_active("data_retention", "2026-11-27")
    assert [c.clause_id for c in active_2026] == ["POL-RET-2026"]

    ctx = idx.format_addressed_context("data_retention", "2026-11-27")
    assert "SUPERSEDED_BY:POL-RET-2026" in ctx
    assert "ACTIVE" in ctx

    # Valid active citation passes
    ok, errs = idx.verify_citations("Logs are kept for 365 days [POL-RET-2026].", "2026-11-27")
    assert ok is True and errs == []

    # Superseded clause & planted fake citation ("Art.999-bis") both rejected deterministically
    ok_bad, errs_bad = idx.verify_citations(
        "Per [POL-RET-2024] and [ART-999-BIS], retention is 90 days.",
        "2026-11-27",
    )
    assert ok_bad is False
    assert "superseded_clause_cited:POL-RET-2024" in errs_bad
    assert "unknown_citation_trap:ART-999-BIS" in errs_bad


def test_docseam_cross_page_table_header_propagation() -> None:
    p1 = "# Portfolio Summary\n| Covenant | Limit |\n|---|---|\n| Leverage | 3.5x |"
    p2 = "| Interest Coverage | 2.0x |\nFootnote: audited quarterly."
    stitched = stitch_cross_page_seams([p1, p2])
    assert len(stitched) == 2
    assert "| Covenant | Limit |" in stitched[1]
    assert "| Interest Coverage | 2.0x |" in stitched[1]
