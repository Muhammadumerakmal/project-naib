import uuid

import httpx
import pytest
from agents.tool_context import ToolContext

from naib.agents.context import NaibContext
from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import Client, EnrichmentCache
from naib.tools.enrichment_tools import (
    detect_stack,
    fetch_page,
    guess_company_domain,
)


def _fake_tool_ctx(
    *, tool_name: str, naib_context: NaibContext | None = None
) -> ToolContext[NaibContext]:
    context = naib_context or NaibContext(
        client=Client(name="x", plan="pilot", playbook_version="v0"),
        lead_id=uuid.uuid4(),
        language="en",
    )
    return ToolContext(
        context=context, tool_name=tool_name, tool_call_id="call-1", tool_arguments="{}"
    )


def test_detect_stack_recognizes_wordpress() -> None:
    assert "WordPress" in detect_stack('<meta name="generator" content="WordPress 6.4">')


def test_detect_stack_recognizes_shopify() -> None:
    assert "Shopify" in detect_stack('<script src="https://cdn.shopify.com/s/files/x.js">')


def test_detect_stack_returns_empty_for_unrecognized_html() -> None:
    assert detect_stack("<html><body>Plain site</body></html>") == []


async def test_guess_company_domain_returns_https_com_url() -> None:
    output = await guess_company_domain.on_invoke_tool(
        _fake_tool_ctx(tool_name="guess_company_domain"), '{"company_name": "Ali Bakery & Co."}'
    )
    assert output == "https://alibakeryco.com"


async def test_fetch_page_serves_from_cache_without_a_network_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = f"https://example.com/cached-page-{uuid.uuid4()}"
    async with get_sessionmaker()() as session:
        session.add(EnrichmentCache(cache_key=url, content="cached content"))
        await session.commit()

    async def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("fetch_page should not hit the network on a cache hit")

    monkeypatch.setattr(httpx.AsyncClient, "get", _boom)

    result = await fetch_page.on_invoke_tool(
        _fake_tool_ctx(tool_name="fetch_page"), f'{{"url": "{url}"}}'
    )

    assert result == "cached content"


async def test_fetch_page_respects_the_enrichment_budget_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "max_enrichment_calls", 1)
    naib_context = NaibContext(
        client=Client(name="x", plan="pilot", playbook_version="v0"),
        lead_id=uuid.uuid4(),
        language="en",
        enrichment_calls=1,
    )

    async def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("fetch_page should not hit the network once the budget is spent")

    monkeypatch.setattr(httpx.AsyncClient, "get", _boom)

    result = await fetch_page.on_invoke_tool(
        _fake_tool_ctx(tool_name="fetch_page", naib_context=naib_context),
        '{"url": "https://example.com/uncached"}',
    )

    assert "budget" in result.lower()
