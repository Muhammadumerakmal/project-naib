"""pgvector nearest-neighbour search over past won proposals, chunked by
scope section (`naib.embeddings.chunk_by_scope_section`). See PLAN.md
Phase 3.
"""

import importlib.resources
import json

from sqlmodel import select

from naib.embeddings import Embedder, chunk_by_scope_section
from naib.schemas.retrieved_chunk import RetrievedChunk
from naib.store.db import get_sessionmaker
from naib.store.models import ProposalChunk


async def search_past_proposals(
    query: str, embedder: Embedder, *, limit: int = 3
) -> list[RetrievedChunk]:
    query_embedding = await embedder.embed(query)

    embedding_column = ProposalChunk.embedding  # why: pgvector comparator, untyped on list[float]
    distance = embedding_column.cosine_distance(query_embedding)  # type: ignore[attr-defined]

    async with get_sessionmaker()() as session:
        statement = (
            select(
                ProposalChunk.proposal_label,
                ProposalChunk.scope_section,
                ProposalChunk.chunk_text,
                distance.label("distance"),
            )
            .order_by(distance)
            .limit(limit)
        )
        rows = (await session.exec(statement)).all()

    return [
        RetrievedChunk(
            proposal_label=proposal_label,
            scope_section=scope_section,
            chunk_text=chunk_text,
            distance=row_distance,
        )
        for proposal_label, scope_section, chunk_text, row_distance in rows
    ]


async def seed_proposal_chunks(
    embedder: Embedder, records: list[tuple[str, str, str, bool]]
) -> None:
    """Embed and insert (proposal_label, scope_section, chunk_text,
    is_synthetic) rows."""

    async with get_sessionmaker()() as session:
        for proposal_label, scope_section, chunk_text, is_synthetic in records:
            embedding = await embedder.embed(chunk_text)
            session.add(
                ProposalChunk(
                    proposal_label=proposal_label,
                    scope_section=scope_section,
                    chunk_text=chunk_text,
                    embedding=embedding,
                    is_synthetic=is_synthetic,
                )
            )
        await session.commit()


async def seed_synthetic_won_proposals(embedder: Embedder) -> None:
    """Load `naib.data.won_proposals_seed.json`, chunk each proposal by
    scope section, and insert. These are clearly-labelled synthetic
    placeholders — real won proposals don't exist until Phase 4 produces
    some and a human approves them; same self-expiring-data pattern as the
    Phase 1 playbook. Not run automatically by tests or CI; call explicitly
    (e.g. from a one-off script) to populate a dev/demo database."""

    raw = importlib.resources.files("naib.data").joinpath("won_proposals_seed.json").read_text(
        "utf-8"
    )
    proposals = json.loads(raw)

    records: list[tuple[str, str, str, bool]] = []
    for proposal in proposals:
        for scope_section, chunk_text in chunk_by_scope_section(proposal["proposal_md"]):
            records.append(
                (proposal["proposal_label"], scope_section, chunk_text, proposal["is_synthetic"])
            )

    await seed_proposal_chunks(embedder, records)
