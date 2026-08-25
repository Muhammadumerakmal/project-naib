import uuid

from naib.sessions import PostgresSession


async def test_postgres_session_round_trip() -> None:
    lead_id = uuid.uuid4()
    session = PostgresSession(lead_id)

    await session.add_items([{"role": "user", "content": "hello"}])
    assert await session.get_items() == [{"role": "user", "content": "hello"}]

    popped = await session.pop_item()
    assert popped == {"role": "user", "content": "hello"}
    assert await session.get_items() == []

    await session.add_items(
        [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    )
    await session.clear_session()
    assert await session.get_items() == []


async def test_postgres_session_is_isolated_per_lead() -> None:
    session_a = PostgresSession(uuid.uuid4())
    session_b = PostgresSession(uuid.uuid4())

    await session_a.add_items([{"role": "user", "content": "only in a"}])

    assert await session_a.get_items() != []
    assert await session_b.get_items() == []
