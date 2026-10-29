import asyncio
import io
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image
from playwright.async_api import async_playwright

from app import agent, server
from app.guard import check_outbound
from app.models import Action, Element, SanitizedSnapshot, Snapshot
from app.prompts import build_observation
from app.rules import ALL_TYPES, Rules, load_rules
from app.sanitizer import sanitize
from app.validator import validate
from app.vault import Vault

AADHAAR = "2345 6789 0124"
PAN = "ABCPE1234F"
VERIFY_TASK = "Ask support to verify my Aadhaar number"
LOCAL = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={"host": "127.0.0.1:8000"})


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(out, "PNG")
    return out.getvalue()


def aadhaar_page() -> Snapshot:
    field = Element("e1", "input", label="Aadhaar", value=AADHAAR, sensitive_type="AADHAAR",
                    sensitive_reason="field named like an aadhaar", box=(10, 10, 80, 20))
    note = Element("e2", "p", text=f"My Aadhaar is {AADHAAR}")
    return Snapshot("http://localhost/", [field, note], f"My Aadhaar is {AADHAAR}", "", png(),
                    [("AADHAAR", (100, 50, 30, 10))])


def with_mode(mode: str) -> Rules:
    rules = Rules()
    rules.modes["AADHAAR"] = mode
    return rules


def test_every_type_defaults_to_ask_and_custom_stays_redact():
    rules = Rules()
    modes = rules.to_dict()["modes"]
    assert list(modes) == ALL_TYPES
    assert {t for t, m in modes.items() if m != "ask"} == {"CUSTOM"}
    assert rules.mode("NOT_A_TYPE") == "ask" and rules.on("CARD")
    assert not with_mode("reveal").on("AADHAAR") and with_mode("redact").on("AADHAAR")


def test_load_rules_ignores_enabled_and_bad_modes(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"enabled": {"EMAIL": False},
                                "modes": {"PAN": "reveal", "EMAIL": "loud", "NOPE": "reveal"}}))
    modes = load_rules(path).to_dict()["modes"]
    assert modes["PAN"] == "reveal" and modes["EMAIL"] == "ask" and "NOPE" not in modes
    assert {t for t, m in load_rules().to_dict()["modes"].items() if m != "ask"} == {"CUSTOM"}


def test_with_shared_returns_a_copy():
    rules = Rules()
    shared = rules.with_shared({"PAN"})
    assert shared.mode("PAN") == "reveal" and rules.mode("PAN") == "ask"


@pytest.mark.parametrize("mode", ["redact", "ask"])
def test_hidden_modes_keep_the_value_out(mode):
    vault = Vault()
    vault.add("AADHAAR", AADHAAR)
    rules = with_mode(mode)
    snap = sanitize(aadhaar_page(), vault, rules)
    assert AADHAAR not in repr((snap.elements, snap.page_text))
    image = Image.open(io.BytesIO(snap.screenshot)).convert("RGB")
    assert image.getpixel((20, 15)) == (0, 0, 0) and image.getpixel((110, 55)) == (0, 0, 0)
    assert not check_outbound(f"page: {AADHAAR}", vault, rules).allowed


def test_reveal_lets_the_value_through_sanitize_and_guard():
    vault = Vault()
    vault.add("AADHAAR", AADHAAR)
    vault.add("PAN", PAN)
    rules = with_mode("reveal")
    snap = sanitize(aadhaar_page(), vault, rules)
    assert snap.page_text == f"My Aadhaar is {AADHAAR}" and snap.elements[0].value == AADHAAR
    image = Image.open(io.BytesIO(snap.screenshot)).convert("RGB")
    assert image.getpixel((20, 15)) == (255, 255, 255) and image.getpixel((110, 55)) == (255, 255, 255)
    assert check_outbound(f"page: {AADHAAR}", vault, rules).allowed
    assert not check_outbound(f"page: {AADHAAR} {PAN}", vault, rules).allowed


def test_canary_and_custom_rules_stay_blocked_when_everything_is_revealed():
    rules = Rules(modes={t: "reveal" for t in ALL_TYPES}, custom=[r"Project Falcon"])
    vault = Vault()
    vault.canaries.add("CANARY-TEST-1")
    vault.add("CARD", "4111111111111111")
    assert check_outbound("card 4111 1111 1111 1111", vault, rules).allowed
    assert not check_outbound("note CANARY-TEST-1", vault, rules).allowed
    assert not check_outbound("about Project Falcon", vault, rules).allowed


def _validate(value: str, rules: Rules, action: str = "reveal", target: str = ""):
    vault = Vault()
    vault.add("AADHAAR", AADHAAR)
    snap = SanitizedSnapshot("http://localhost/", [Element("e2", "textarea", label="Message", can_type=True)],
                             "", "", b"", [])
    return validate(Action(action, target, value), snap, vault, rules)


def test_reveal_action_needs_ask_mode():
    hidden = _validate("{{AADHAAR#1}}", with_mode("redact"))
    assert not hidden.ok and hidden.reason == "That kind of data is set to stay hidden."
    asked = _validate("{{AADHAAR#1}}", with_mode("ask"))
    assert asked.ok and asked.needs_approval
    again = _validate("{{AADHAAR#1}}", with_mode("ask").with_shared({"AADHAAR"}))
    assert again.ok and not again.needs_approval
    assert not _validate("{{AADHAAR#9}}", with_mode("ask")).ok


def test_revealed_literal_may_be_typed_but_hidden_one_may_not():
    assert _validate(f"My ID is {AADHAAR}", with_mode("reveal"), "type", "e2").ok
    assert not _validate(f"My ID is {AADHAAR}", with_mode("ask"), "type", "e2").ok


def test_ask_kinds_lists_only_unshared_kinds_with_a_token():
    vault = Vault()
    vault.add("AADHAAR", AADHAAR)
    vault.add("PAN", PAN)
    snap = SanitizedSnapshot("http://localhost/", [], "", "", b"", [])
    rules = Rules().with_shared({"PAN"})
    assert json.loads(build_observation("t", snap, vault, [], rules))["ask_kinds"] == ["AADHAAR"]


def test_shared_types_do_not_carry_over_to_the_next_task():
    rules = Rules()
    rules.modes["EMAIL"] = "reveal"
    first = agent.Session("support", "t", "mock", rules)
    first.shared_types.add("AADHAAR")
    assert first.shared() == [{"type": "EMAIL", "by": "choice"}, {"type": "AADHAAR", "by": "approval"}]
    second = agent.Session("support", "t", "mock", rules)
    assert second.shared_types == set() and rules.mode("AADHAAR") == "ask"


async def _support_run(base_url: str, task: str, approve: bool):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        session = agent.Session("support", task, "mock", Rules())
        await session.start(browser, base_url)
        run = asyncio.create_task(agent.run(session))
        asked = []
        while not run.done():
            if session.approval is not None and session.approval_answer is None:
                asked.append(dict(session.approval))
                session.answer(approve)
            await asyncio.sleep(0.05)
        await run
        await session.close()
        await browser.close()
    return session, asked


def test_approved_share_reaches_the_ai_from_the_next_step(base_url):
    session, asked = asyncio.run(_support_run(base_url, VERIFY_TASK, approve=True))
    assert asked[0] == {"question": "Let the AI read your Aadhaar number for this task?", "kind": "share",
                        "why": "You chose to be asked before this is shared. It will be shared for this task only."}
    assert session.shared_types == {"AADHAAR"} and session.success
    first, *later = session.llm.payloads
    assert AADHAAR not in first and any(AADHAAR in p for p in later)
    assert not any(PAN in p for p in session.llm.payloads)


def test_cancelled_share_stops_the_run(base_url):
    session, asked = asyncio.run(_support_run(base_url, VERIFY_TASK, approve=False))
    assert asked[0]["kind"] == "share" and session.narration == "Stopped: stopped by you."
    assert session.shared_types == set() and not any(AADHAAR in p for p in session.llm.payloads)


@pytest.fixture
def fresh_state(monkeypatch):
    monkeypatch.setattr(server, "state", server.State(rules=Rules(), ai="mock"))
    monkeypatch.setattr(server, "save_rules", lambda rules: None)
    return server.state


def test_put_rules_merges_modes_and_rejects_bad_ones(fresh_state):
    server.put_rules(LOCAL, {"modes": {"AADHAAR": "reveal"}})
    result = server.put_rules(LOCAL, {"modes": {"CARD": "redact"}})
    assert result["modes"]["AADHAAR"] == "reveal" and result["modes"]["CARD"] == "redact"
    assert result == server.get_rules() and set(result) == {"modes", "hints", "custom"}
    with pytest.raises(HTTPException) as err:
        server.put_rules(LOCAL, {"modes": {"CARD": "show"}})
    assert err.value.status_code == 400 and fresh_state.rules.mode("CARD") == "redact"
