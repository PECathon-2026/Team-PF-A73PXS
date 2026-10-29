import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import agent, server
from app.rules import Rules

LOCAL = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={"host": "127.0.0.1:8000"})


@pytest.fixture
def fresh_state(monkeypatch):
    monkeypatch.setattr(server, "state", server.State(rules=Rules(), ai="mock"))
    monkeypatch.setattr(server, "save_rules", lambda rules: None)
    return server.state


def test_unknown_scenario_is_a_400(fresh_state):
    with pytest.raises(HTTPException) as err:
        asyncio.run(server.start_session(LOCAL, {"scenario": "nope"}))
    assert err.value.status_code == 400


def test_unknown_ai_is_a_400(fresh_state):
    with pytest.raises(HTTPException) as err:
        server.set_ai(LOCAL, {"ai": "other"})
    assert err.value.status_code == 400
    assert server.set_ai(LOCAL, {"ai": "mock_fooled"})["ai"] == "mock_fooled"


@pytest.mark.parametrize("body", [
    {"custom": "Project Falcon"},
    {"custom": [1]},
    {"modes": {"NOT_A_TYPE": "ask"}},
    {"modes": {"EMAIL": "no"}},
    {"modes": {"EMAIL": True}},
    {"modes": ["EMAIL"]},
    {"modes": {"CUSTOM": "reveal"}},
    {"hints": ["CARD"]},
    {"hints": {"CARD": 1}},
])
def test_put_rules_rejects_bad_types(fresh_state, body):
    with pytest.raises(HTTPException) as err:
        server.put_rules(LOCAL, body)
    assert err.value.status_code == 400


def test_put_rules_merges_hints(fresh_state):
    server.put_rules(LOCAL, {"hints": {"CARD": True}})
    result = server.put_rules(LOCAL, {"hints": {"EMAIL": False}})
    assert result["hints"] == {"CARD": True, "EMAIL": False}


def test_back_to_back_sessions_cancel_the_first_run(fresh_state, monkeypatch):
    async def no_browser(self, browser, base_url):
        return None

    async def endless_run(session):
        await asyncio.sleep(3600)

    monkeypatch.setattr(agent.Session, "start", no_browser)
    monkeypatch.setattr(agent, "run", endless_run)
    monkeypatch.setattr(server.app.state, "browser", None, raising=False)

    async def scenario():
        await server.start_session(LOCAL, {"scenario": "checkout"})
        first_task, first_session = fresh_state.run_task, fresh_state.session
        await server.start_session(LOCAL, {"scenario": "login"})
        assert first_task.done() and first_task.cancelled()
        assert first_session.vault.values() == []
        assert fresh_state.session is not first_session
        await server._end_session()

    asyncio.run(scenario())


def test_leak_test_without_a_session_blocks_and_keeps_the_canary_out(fresh_state):
    result = asyncio.run(server.leak_test(LOCAL))
    assert result == {"blocked": True}
    session = fresh_state.session
    assert session.blocked and session.page is None and fresh_state.run_task is None
    assert agent.LEAK_CANARY not in session.vault.canaries
