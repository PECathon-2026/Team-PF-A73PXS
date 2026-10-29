import json

import httpx
import pytest

from app import llm
from app.llm import GeminiLLM, LLMError, first_json_object

ACTION = {"action": "click", "target": "e1", "value": "", "reason": "go"}


def answer(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


@pytest.fixture
def gemini(monkeypatch):
    """A GeminiLLM whose requests go to a script of fake responses instead of the network."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "main")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "spare1, spare2")
    sleeps: list[float] = []
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    monkeypatch.setattr(llm.random, "uniform", lambda a, b: 0)
    calls: list[str] = []
    script: list = []

    def post(url, **kwargs):
        calls.append(url.split("/models/")[1].split(":")[0])
        step = script.pop(0)
        if isinstance(step, Exception):
            raise step
        status, payload, headers = step
        content = json.dumps(payload) if isinstance(payload, dict) else payload
        return httpx.Response(status, content=content, headers=headers, request=httpx.Request("POST", url))

    monkeypatch.setattr(llm.httpx, "post", post)
    provider = GeminiLLM()
    provider.script, provider.calls, provider.sleeps = script, calls, sleeps
    return provider


def test_main_model_answers_without_fallback(gemini):
    gemini.script.append((200, answer(json.dumps(ACTION)), {}))
    assert json.loads(gemini.next_action("sys", "obs")) == ACTION
    assert gemini.calls == ["main"] and gemini.model_used == "main"


def test_busy_main_model_falls_back_in_order_and_records_the_model(gemini):
    gemini.script += [(429, {}, {}), (503, {}, {}), (200, answer(json.dumps(ACTION)), {})]
    gemini.next_action("sys", "obs")
    assert gemini.calls == ["main", "spare1", "spare2"]
    assert gemini.model_used == "spare2" and gemini.sleeps == []


def test_each_round_starts_again_with_the_main_model(gemini):
    gemini.script += [httpx.ReadTimeout("slow")] * 3 + [(200, answer(json.dumps(ACTION)), {})]
    gemini.next_action("sys", "obs")
    assert gemini.calls == ["main", "spare1", "spare2", "main"]
    assert gemini.model_used == "main"


def test_retry_after_header_and_body_delay_set_the_wait(gemini):
    body = {"error": {"details": [{"retryDelay": "9s"}]}}
    gemini.script += [(429, {}, {"Retry-After": "12"}), (429, body, {}), (503, {}, {}),
                      (200, answer(json.dumps(ACTION)), {})]
    gemini.next_action("sys", "obs")
    assert gemini.sleeps == [12]


def test_a_used_up_daily_quota_drops_the_model_for_the_run(gemini):
    daily = {"error": {"details": [{"retryDelay": "38000s"}]}}
    gemini.script += [(429, daily, {}), (429, {}, {"Retry-After": "30"}), (503, {}, {}),
                      (200, answer(json.dumps(ACTION)), {}), (200, answer(json.dumps(ACTION)), {})]
    gemini.next_action("sys", "obs")
    assert gemini.models == ["spare1", "spare2"] and gemini.sleeps == [llm.MAX_WAIT_SECONDS]
    gemini.next_action("sys", "obs")
    assert gemini.calls[-1] == "spare1"


def test_stops_at_once_when_every_model_is_out_of_quota(gemini):
    gemini.script += [(429, {}, {"Retry-After": "3600"})] * 3
    with pytest.raises(LLMError):
        gemini.next_action("sys", "obs")
    assert len(gemini.calls) == 3 and gemini.sleeps == []


def test_gives_up_after_every_round_is_busy(gemini):
    gemini.script += [(503, {}, {})] * 9
    with pytest.raises(LLMError, match="could not be reached"):
        gemini.next_action("sys", "obs")
    assert len(gemini.calls) == 9 and gemini.sleeps == [2, 6]


def test_empty_candidates_and_safety_blocks_are_retried(gemini):
    blocked = {"promptFeedback": {"blockReason": "SAFETY"}}
    no_text = {"candidates": [{"finishReason": "SAFETY"}]}
    gemini.script += [(200, blocked, {}), (200, no_text, {}), (200, answer("  "), {}),
                      (200, answer(json.dumps(ACTION)), {})]
    assert json.loads(gemini.next_action("sys", "obs")) == ACTION
    assert gemini.calls == ["main", "spare1", "spare2", "main"]


def test_bad_request_on_the_main_model_stops_at_once(gemini):
    gemini.script.append((400, {}, {}))
    with pytest.raises(LLMError, match="rejected"):
        gemini.next_action("sys", "obs")
    assert gemini.calls == ["main"]


def test_unusable_fallback_is_dropped(gemini):
    gemini.script += [(429, {}, {}), (404, {}, {}), (200, answer(json.dumps(ACTION)), {})]
    gemini.next_action("sys", "obs")
    assert gemini.models == ["main", "spare2"]


def test_thought_parts_are_left_out(gemini):
    data = {"candidates": [{"content": {"parts": [{"text": "{\"action\": \"wait\"}", "thought": True},
                                                  {"text": json.dumps(ACTION)}]}}]}
    gemini.script.append((200, data, {}))
    assert json.loads(gemini.next_action("sys", "obs")) == ACTION


def test_fallbacks_default_and_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
    monkeypatch.delenv("GEMINI_FALLBACK_MODELS", raising=False)
    assert GeminiLLM().models == ["gemini-3.6-flash", "gemini-3.5-flash"]
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
    assert GeminiLLM().models == ["gemini-3.6-flash"]


@pytest.mark.parametrize("text", [
    '```json\n{"action": "click", "target": "e1", "value": "", "reason": "go"}\n```',
    'Here you go: {"action": "click", "target": "e1", "value": "", "reason": "go"} done.',
    '[{"action": "click", "target": "e1", "value": "", "reason": "go"}]',
])
def test_first_json_object_is_found_in_fenced_or_wrapped_text(text):
    assert json.loads(first_json_object(text)) == ACTION


def test_text_without_json_is_passed_on_for_the_validator_to_reject():
    assert first_json_object("I am not sure {what to do") == "I am not sure {what to do"
