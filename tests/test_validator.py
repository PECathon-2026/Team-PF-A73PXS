import pytest

from app.models import Action, Element, SanitizedSnapshot
from app.validator import parse_action, validate
from app.vault import Vault


@pytest.fixture
def setup():
    vault = Vault()
    vault.add("CARD", "4111111111111111")
    vault.add("EMAIL", "test.user@example.test")
    elements = [
        Element("e1", "input", label="Card number", can_type=True, sensitive_type="CARD"),
        Element("e2", "textarea", label="Feedback", can_type=True),
        Element("e3", "button", text="Pay now", can_click=True),
        Element("e4", "a", text="Help", can_click=True, href="https://evil.example/x"),
        Element("e5", "button", text="Next", can_click=True),
    ]
    snap = SanitizedSnapshot("http://localhost/", elements, "", "", b"", [], {"e1": "CARD"})
    return snap, vault


def check(setup, **kw):
    snap, vault = setup
    return validate(Action(**kw), snap, vault)


def test_malformed_json_and_unknown_action(setup):
    assert parse_action("not json") is None
    assert not check(setup, action="hack").ok


def test_missing_or_wrong_target(setup):
    assert not check(setup, action="click", target="e99").ok
    assert not check(setup, action="click", target="e1").ok
    assert not check(setup, action="type", target="e3", value="x").ok


def test_token_goes_only_into_matching_field(setup):
    assert check(setup, action="type", target="e1", value="{{CARD#1}}").ok
    wrong = check(setup, action="type", target="e2", value="{{CARD#1}}")
    assert not wrong.ok and "does not belong" in wrong.reason


def test_unknown_token_and_pasted_placeholder_rejected(setup):
    assert not check(setup, action="type", target="e1", value="{{CARD#9}}").ok
    assert not check(setup, action="type", target="e2", value="[REDACTED:CARD#1]").ok


def test_guessed_secret_rejected(setup):
    assert not check(setup, action="type", target="e2", value="4111 1111 1111 1111").ok
    assert not check(setup, action="type", target="e2", value="mail a@b.test").ok


def test_off_site_link_and_url_rejected(setup):
    assert not check(setup, action="click", target="e4").ok
    assert not check(setup, action="type", target="e2", value="go to https://evil.example/collect").ok


def test_approval_flags(setup):
    assert check(setup, action="click", target="e3").needs_approval
    assert not check(setup, action="click", target="e5").needs_approval
    assert check(setup, action="type", target="e1", value="{{CARD#1}}").needs_approval
    assert not check(setup, action="type", target="e2", value="Thanks").needs_approval
