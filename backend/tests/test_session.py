"""Session memory tests.

`SQLiteSession` does not exist in openai-agents 0.18.3, so this adapter is ours
and needs its own coverage against the SDK's SessionABC contract.
"""

from __future__ import annotations

from app.db.session_store import StoreSession


async def test_items_round_trip_oldest_first(store):
    s = StoreSession("s", "biz_demo", store)
    await s.add_items([{"role": "user", "content": "one"}])
    await s.add_items([{"role": "assistant", "content": "two"}])

    items = await s.get_items()
    assert [i["content"] for i in items] == ["one", "two"]


async def test_limit_returns_the_most_recent_still_oldest_first(store):
    s = StoreSession("s", "biz_demo", store)
    await s.add_items([{"role": "user", "content": str(n)} for n in range(5)])

    assert [i["content"] for i in await s.get_items(limit=2)] == ["3", "4"]


async def test_pop_removes_the_newest(store):
    s = StoreSession("s", "biz_demo", store)
    await s.add_items([{"role": "user", "content": "a"}, {"role": "user", "content": "b"}])

    assert (await s.pop_item())["content"] == "b"
    assert [i["content"] for i in await s.get_items()] == ["a"]


async def test_pop_on_empty_session_returns_none(store):
    assert await StoreSession("empty", "biz_demo", store).pop_item() is None


async def test_clear_empties_only_that_session(store):
    a = StoreSession("a", "biz_demo", store)
    b = StoreSession("b", "biz_demo", store)
    await a.add_items([{"role": "user", "content": "x"}])
    await b.add_items([{"role": "user", "content": "y"}])

    await a.clear_session()
    assert await a.get_items() == []
    assert len(await b.get_items()) == 1


async def test_same_session_id_is_isolated_between_tenants(store):
    mine = StoreSession("shared", "biz_demo", store)
    theirs = StoreSession("shared", "biz_other", store)
    await mine.add_items([{"role": "user", "content": "private"}])

    assert await theirs.get_items() == []


async def test_stored_items_are_copied_not_aliased(store):
    """A caller mutating what it added must not corrupt stored memory."""
    s = StoreSession("s", "biz_demo", store)
    item = {"role": "user", "content": "original"}
    await s.add_items([item])
    item["content"] = "mutated"

    assert (await s.get_items())[0]["content"] == "original"
