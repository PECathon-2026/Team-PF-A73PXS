import json
import os
import time
from collections.abc import Iterator

import httpx


RETRY_SECONDS = (2, 6, 15)


class LLMError(Exception):
    pass


class MockLLM:
    """Scripted, offline planner. Reads only the sanitized observation it is given."""

    name = "mock"

    def __init__(self, gullible: bool = False) -> None:
        self.gullible = gullible

    def next_action(self, system: str, observation: str) -> str:
        obs = json.loads(observation)
        done = {(h["action"], h["label"], h["value"]) for h in obs["history"] if h["result"].startswith("ok")}
        for action in self._plan(obs):
            if (action["action"], action["label"], action["value"]) not in done:
                return json.dumps({k: v for k, v in action.items() if k != "label"})
        return json.dumps({"action": "done", "reason": "the task looks complete"})

    def _plan(self, obs: dict) -> Iterator[dict]:
        task = obs["task"].lower()
        if self.gullible and "card" in obs["page_text"].lower():
            yield from self._paste_card(obs)
        if "pay" in task:
            yield from self._fill_all(obs)
            yield from self._click(obs, "pay")
        elif "log me in" in task:
            yield from self._fill_all(obs)
            yield from self._click(obs, "sign in")
            yield from self._fill_all(obs)
            yield from self._click(obs, "verify")
        elif "support" in task:
            yield from self._type(obs, "message", "Hello, could you tell me the status of my order?")
            yield from self._click(obs, "send")
        elif "mute" in task:
            yield from self._click(obs, "mute all")
            yield from self._click(obs, "copy")
        elif "rotate" in task:
            yield from self._click(obs, "rotate")
            yield from self._click(obs, "two-factor")
        elif "feedback" in task:
            yield from self._type(obs, "feedback", "Thanks, the service was great.")
            yield from self._click(obs, "submit")

    def _find(self, obs: dict, words: str, key: str) -> dict | None:
        for e in obs["elements"]:
            if e[key] and all(w in f"{e['label']} {e['text']}".lower() for w in words.split()):
                return e
        return None

    def _click(self, obs: dict, words: str) -> Iterator[dict]:
        e = self._find(obs, words, "can_click")
        if e:
            yield {"action": "click", "target": e["id"], "value": "", "label": e["label"] or e["text"],
                   "reason": f"click {words}"}

    def _type(self, obs: dict, words: str, text: str) -> Iterator[dict]:
        e = self._find(obs, words, "can_type")
        if e:
            yield {"action": "type", "target": e["id"], "value": text, "label": e["label"] or e["text"],
                   "reason": f"write in {words}"}

    def _fill_all(self, obs: dict) -> Iterator[dict]:
        tokens = {s["kind"]: s["token"] for s in reversed(obs["secrets"])}
        for e in obs["elements"]:
            if e["can_type"] and not e["value"] and e["expects"] in tokens:
                yield {"action": "type", "target": e["id"], "value": tokens[e["expects"]],
                       "label": e["label"] or e["text"], "reason": "fill with saved detail"}

    def _paste_card(self, obs: dict) -> Iterator[dict]:
        card = next((s["token"] for s in obs["secrets"] if s["kind"] == "CARD"), None)
        box = self._find(obs, "feedback", "can_type")
        if card and box:
            yield {"action": "type", "target": box["id"], "value": card, "label": "injected", "reason": "page asked"}


class RecordingLLM:
    """Wraps a provider and keeps every payload it was given, for the leak tests."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.name = inner.name
        self.payloads: list[str] = []

    def next_action(self, system: str, observation: str) -> str:
        self.payloads.append(system + "\n" + observation)
        return self.inner.next_action(system, observation)


class GeminiLLM:
    name = "gemini"
    url = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self) -> None:
        self.key = os.getenv("GEMINI_API_KEY", "")
        self.model = os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite"
        if not self.key:
            raise LLMError("no Gemini key in .env")

    def next_action(self, system: str, observation: str) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": observation}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        for attempt, pause in enumerate(RETRY_SECONDS, start=1):
            try:
                r = httpx.post(self.url.format(model=self.model), json=body, timeout=30,
                               headers={"x-goog-api-key": self.key})
                r.raise_for_status()
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500 and exc.response.status_code != 429:
                    raise LLMError("the AI service rejected the request") from None
            except (httpx.HTTPError, KeyError, IndexError, ValueError):
                pass
            if attempt < len(RETRY_SECONDS):
                time.sleep(pause)
        raise LLMError("the AI service could not be reached")


def get_llm(name: str):
    if name == "gemini":
        return GeminiLLM()
    return MockLLM(gullible=name == "mock_fooled")
