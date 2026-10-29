import json
import os
import random
import re
import time
from collections.abc import Iterator

import httpx


RETRY_SECONDS = (2, 6, 15)
MAX_WAIT_SECONDS = 30
TIMEOUT_SECONDS = 30
# gemini-3.8-flash is listed for this key but did not answer within 90 s when tested, so it is not a default.
DEFAULT_FALLBACK_MODELS = ("gemini-3.6-flash", "gemini-3.5-flash")
# Gemini puts the suggested wait in the body of a 429 ("retryDelay": "17s") as well as, sometimes, a header.
RETRY_DELAY = re.compile(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"')


class LLMError(Exception):
    pass


class Busy(Exception):
    """A failure worth trying again: rate limit, overload, timeout, or an answer with no text."""

    def __init__(self, wait: float = 0) -> None:
        super().__init__()
        self.wait = wait


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
            # Only a task that asks for verification needs an ID, so the default support task never asks to see one.
            if "verify" in task:
                yield from self._reveal(obs)
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

    def _reveal(self, obs: dict) -> Iterator[dict]:
        """Ask to read a hidden detail the task names, if the user set it to Ask; next_action skips any
        already revealed."""
        task = obs["task"].lower()
        tokens = {s["kind"]: s["token"] for s in reversed(obs["secrets"])}
        for kind in obs.get("ask_kinds", []):
            if kind in tokens and kind.lower().replace("_", " ") in task:
                yield {"action": "reveal", "target": "", "value": tokens[kind], "label": "",
                       "reason": f"the task needs the {kind.lower()}"}

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

    @property
    def model_used(self) -> str:
        """The model that wrote the last answer; providers with one model report their name."""
        return getattr(self.inner, "model_used", "") or self.name

    def next_action(self, system: str, observation: str) -> str:
        self.payloads.append(system + "\n" + observation)
        return self.inner.next_action(system, observation)


def fallback_models() -> list[str]:
    configured = os.getenv("GEMINI_FALLBACK_MODELS")
    names = DEFAULT_FALLBACK_MODELS if configured is None else configured.split(",")
    return [n.strip() for n in names if n.strip()]


def retry_after(response: httpx.Response) -> float:
    """Seconds the service asked us to wait, from the Retry-After header or the 429 body; 0 if it did not say."""
    header = response.headers.get("retry-after", "")
    if header.replace(".", "", 1).isdigit():
        return float(header)
    found = RETRY_DELAY.search(response.text)
    return float(found[1]) if found else 0


def first_json_object(text: str) -> str:
    """The first JSON object in the text, so code fences or a sentence around it do not cost a step.
    Text without one is returned as is and rejected by the validator."""
    decoder = json.JSONDecoder()
    for start in (i for i, c in enumerate(text) if c == "{"):
        try:
            found, _ = decoder.raw_decode(text, start)
        except ValueError:
            continue
        if isinstance(found, dict):
            return json.dumps(found)
    return text


def reply_text(data: dict) -> str:
    """The answer text without thought parts. Raises Busy when there is none, such as a blocked prompt."""
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    except (KeyError, IndexError, TypeError, AttributeError):
        raise Busy() from None
    if not text.strip():
        raise Busy()
    return first_json_object(text)


class GeminiLLM:
    name = "gemini"
    url = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self) -> None:
        self.key = os.getenv("GEMINI_API_KEY", "")
        self.model = os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite"
        if not self.key:
            raise LLMError("no Gemini key in .env")
        self.models = list(dict.fromkeys([self.model, *fallback_models()]))
        self.model_used = ""

    def next_action(self, system: str, observation: str) -> str:
        """Each round tries the main model first, then the fallbacks, so a rate limit on one model
        does not end the run. model_used records which model answered."""
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": observation}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        for attempt, pause in enumerate(RETRY_SECONDS, start=1):
            wait = pause
            for model in list(self.models):
                try:
                    reply = self._ask(model, body)
                except Busy as busy:
                    wait = max(wait, busy.wait)
                    continue
                self.model_used = model
                return reply
            if not self.models:
                break
            if attempt < len(RETRY_SECONDS):
                time.sleep(wait + random.uniform(0, 1))
        raise LLMError("the AI service could not be reached")

    def _ask(self, model: str, body: dict) -> str:
        try:
            r = httpx.post(self.url.format(model=model), json=body, timeout=TIMEOUT_SECONDS,
                           headers={"x-goog-api-key": self.key})
        except httpx.HTTPError:
            raise Busy() from None
        if r.status_code == 429 or r.status_code >= 500:
            wait = retry_after(r)
            if wait <= MAX_WAIT_SECONDS:
                raise Busy(wait)
            # A longer wait means a used-up daily quota, so this model sits out the rest of the run.
            self.models.remove(model)
            raise Busy()
        if r.status_code != 200:
            if model == self.model:
                raise LLMError("the AI service rejected the request")
            # A fallback this key cannot use (unknown name, no access) is dropped for the rest of the run.
            self.models.remove(model)
            raise Busy()
        try:
            data = r.json()
        except ValueError:
            raise Busy() from None
        return reply_text(data)


def get_llm(name: str):
    if name == "gemini":
        return GeminiLLM()
    return MockLLM(gullible=name == "mock_fooled")
