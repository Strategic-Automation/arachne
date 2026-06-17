import pytest

import arachne.tools.web.arxiv_search as arxiv_module


@pytest.mark.asyncio
async def test_queued_arxiv_results_waits_between_requests(monkeypatch):
    sleeps = []
    times = iter([100.0, 100.0, 101.0, 101.0])

    monkeypatch.setattr(arxiv_module.time, "monotonic", lambda: next(times))

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    async def fake_to_thread(func, *args):
        return func(*args)

    def fake_fetch(_client, _search_obj):
        return ["ok"]

    monkeypatch.setattr(arxiv_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(arxiv_module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(arxiv_module, "_fetch_arxiv_results", fake_fetch)
    monkeypatch.setattr(arxiv_module, "_last_arxiv_request_started_at", 0.0)

    assert await arxiv_module._queued_arxiv_results(object(), object()) == ["ok"]
    assert await arxiv_module._queued_arxiv_results(object(), object()) == ["ok"]

    assert sleeps == [2.0]
