from naib.embeddings import EMBEDDING_MODEL, chunk_by_scope_section
from naib.store.models import EMBEDDING_DIM


def test_embedding_model_width_matches_the_pgvector_column() -> None:
    """text-embedding-3-small outputs 1536 dims by default — must match
    naib.store.models.EMBEDDING_DIM, or inserts fail with an opaque
    pgvector dimension-mismatch error instead of a clear one here."""

    assert EMBEDDING_MODEL == "text-embedding-3-small"
    assert EMBEDDING_DIM == 1536


def test_chunk_by_scope_section_splits_on_headers() -> None:
    chunks = chunk_by_scope_section(
        "## Scope: Website\nBuild a 5-page site.\n\n## Scope: Timeline\nTwo weeks.\n"
    )
    assert chunks == [
        ("Scope: Website", "Build a 5-page site."),
        ("Scope: Timeline", "Two weeks."),
    ]


def test_chunk_by_scope_section_keeps_intro_before_first_header() -> None:
    chunks = chunk_by_scope_section("Some preamble.\n\n## Scope: Website\nBuild a site.\n")
    assert chunks[0] == ("intro", "Some preamble.")
    assert chunks[1] == ("Scope: Website", "Build a site.")


def test_chunk_by_scope_section_returns_one_intro_chunk_with_no_headers() -> None:
    assert chunk_by_scope_section("Just plain text, no headers.") == [
        ("intro", "Just plain text, no headers.")
    ]


def test_chunk_by_scope_section_returns_empty_for_blank_input() -> None:
    assert chunk_by_scope_section("") == []
    assert chunk_by_scope_section("   \n  ") == []
