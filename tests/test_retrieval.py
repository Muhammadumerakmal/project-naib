"""Tests share the `proposal_chunks` table with every other test in the
session (no per-test truncation fixture exists) — labels are uuid-suffixed
and lookups are by label rather than by absolute top-N position, so these
stay correct regardless of what other tests have inserted before them.
"""

import uuid

from naib.retrieval import search_past_proposals, seed_proposal_chunks


class _FixedEmbedder:
    """Returns a caller-supplied vector regardless of input text, so a test
    can construct exact nearest-neighbour relationships deterministically."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    async def embed(self, text: str) -> list[float]:
        return self._vector


def _vec(*, near: float) -> list[float]:
    return [near] * 1536


async def test_search_past_proposals_returns_nearest_neighbour_first() -> None:
    close_embedder = _FixedEmbedder(_vec(near=0.9))
    far_embedder = _FixedEmbedder(_vec(near=-0.9))
    query_embedder = _FixedEmbedder(_vec(near=1.0))

    close_label = f"Close-{uuid.uuid4()}"
    far_label = f"Far-{uuid.uuid4()}"
    await seed_proposal_chunks(close_embedder, [(close_label, "Scope: A", "A close chunk", True)])
    await seed_proposal_chunks(far_embedder, [(far_label, "Scope: B", "A far chunk", True)])

    results = await search_past_proposals("anything", query_embedder, limit=10_000)
    by_label = {r.proposal_label: r for r in results}

    assert by_label[close_label].distance < by_label[far_label].distance


async def test_search_past_proposals_respects_limit() -> None:
    embedder = _FixedEmbedder(_vec(near=0.5))
    label = f"Limit-{uuid.uuid4()}"
    await seed_proposal_chunks(
        embedder,
        [
            (label, "Scope: A", "chunk 1", True),
            (label, "Scope: A", "chunk 2", True),
            (label, "Scope: A", "chunk 3", True),
        ],
    )

    results = await search_past_proposals("anything", embedder, limit=1)

    assert len(results) == 1
