"""Embedding provider + proposal chunking for `RetrievalAgent`'s pgvector
search. `Embedder` is a Protocol so tests never call a real (paid) API —
same pattern as `naib.voice.transcription.Transcriber`. See PLAN.md Phase 3.
"""

import re
from typing import Protocol

from openai import AsyncOpenAI

from naib.settings import get_settings

# 1536-dimensional output — must match naib.store.models.EMBEDDING_DIM,
# which the pgvector column is declared against (checked by
# tests/test_embeddings.py so a mismatch surfaces immediately, not as an
# opaque pgvector dimension error at insert time).
EMBEDDING_MODEL = "text-embedding-3-small"

# A proposal's scope is written as markdown sections ("## Scope: ..."), and
# PLAN.md is explicit: chunk by scope section, not arbitrary character
# count, so retrieved excerpts stay coherent.
_SECTION_HEADER = re.compile(r"^##\s+(.+)$", re.MULTILINE)


class Embedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class OpenAIEmbedder:
    """Constructing this must never require a live API key — QualifierAgent
    is built (and RetrievalAgent's tool wired up) on every lead, whether or
    not the model ever actually calls the retrieval tool. The OpenAI client
    is built lazily on first `embed()` call instead."""

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=get_settings().openai_api_key)
        return self._client

    async def embed(self, text: str) -> list[float]:
        response = await self._get_client().embeddings.create(model=EMBEDDING_MODEL, input=text)
        return response.data[0].embedding


def chunk_by_scope_section(proposal_md: str) -> list[tuple[str, str]]:
    """Split a proposal's markdown body into (section_title, chunk_text)
    pairs at `## ` headers. Text before the first header, if any, is
    returned under the section title "intro"."""

    headers = list(_SECTION_HEADER.finditer(proposal_md))
    if not headers:
        return [("intro", proposal_md.strip())] if proposal_md.strip() else []

    chunks: list[tuple[str, str]] = []
    intro = proposal_md[: headers[0].start()].strip()
    if intro:
        chunks.append(("intro", intro))

    for i, header in enumerate(headers):
        title = header.group(1).strip()
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(proposal_md)
        body = proposal_md[start:end].strip()
        if body:
            chunks.append((title, body))

    return chunks
