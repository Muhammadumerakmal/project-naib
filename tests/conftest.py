"""Test DB setup. Requires a real Postgres reachable at settings.database_url
(docker compose up postgres, or CI's postgres service). Unit tests are
deterministic logic against real infra, not mocks — there is no in-memory
Postgres substitute that would prove the async driver / JSONB columns work.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from naib.store import models  # noqa: F401  (registers tables on SQLModel.metadata)
from naib.store.db import get_engine, get_sessionmaker


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema() -> AsyncIterator[None]:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    from naib.settings import get_settings

    get_settings.cache_clear()
