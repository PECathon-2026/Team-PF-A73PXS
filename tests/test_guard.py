import io

from PIL import Image

from app.guard import check_outbound
from app.models import Element, Snapshot
from app.rules import Rules
from app.sanitizer import sanitize
from app.scrub import scrub
from app.vault import Vault

CARD = "4111 1111 1111 1111"


def png(size=(200, 100)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, "white").save(out, "PNG")
    return out.getvalue()


def snapshot() -> Snapshot:
    card = Element("e1", "input", label="Card number", value=CARD, input_type="cc-number",
                   sensitive_type="CARD", sensitive_reason="card number field", box=(10, 10, 80, 20))
    note = Element("e2", "p", text=f"Call +91 98765 43210 about order 1234 or card {CARD}")
    return Snapshot("http://localhost/?email=a.b@example.test", [card, note],
                    f"Pay with {CARD}", "", png(), [("PHONE", (100, 50, 30, 10))])


def test_sanitized_output_has_no_raw_values():
    vault = Vault()
    snap = sanitize(snapshot(), vault, Rules())
    blob = repr((snap.elements, snap.page_text, snap.url))
    for secret in ("4111", "98765", "a.b@example.test"):
        assert secret not in blob
    assert "[REDACTED:CARD#1]" in snap.page_text
    assert len(snap.report) >= 3


def test_same_value_same_placeholder():
    vault = Vault()
    snap = sanitize(snapshot(), vault, Rules())
    assert snap.elements[0].value == snap.elements[1].text.split("card ")[1]


def test_screenshot_is_blacked_out():
    snap = sanitize(snapshot(), Vault(), Rules())
    image = Image.open(io.BytesIO(snap.screenshot)).convert("RGB")
    assert image.getpixel((20, 15)) == (0, 0, 0)
    assert image.getpixel((110, 55)) == (0, 0, 0)
    assert image.getpixel((190, 95)) == (255, 255, 255)


def test_hint_has_no_digits():
    rules = Rules(hints={"CARD": True})
    snap = sanitize(snapshot(), Vault(), rules)
    assert "[REDACTED:CARD#1 - Visa]" in snap.page_text


def test_guard_blocks_raw_vault_value_and_variants():
    vault = Vault()
    vault.add("CARD", CARD)
    for leak in (CARD, "4111111111111111", "4111-1111-1111-1111", "4​111 1111 1111 1111"):
        assert not check_outbound(f"hello {leak}", vault).allowed


def test_guard_blocks_canary_and_short_value_as_whole_word():
    vault = Vault()
    vault.canaries.add("CANARY-7Q2X9-A")
    vault.add("CVV", "123")
    assert not check_outbound("x CANARY-7Q2X9-A", vault).allowed
    assert not check_outbound("cvv is 123", vault).allowed
    assert check_outbound("element e1231 at 4123", vault).allowed


def test_guard_blocks_unredacted_pattern_not_in_vault():
    assert not check_outbound("mail me at someone@example.test", Vault()).allowed


def test_guard_allows_clean_payload():
    assert check_outbound("Click [REDACTED:CARD#1] total 1,499", Vault()).allowed


def test_guard_fails_closed(monkeypatch):
    def boom(*_):
        raise RuntimeError("boom")
    monkeypatch.setattr("app.guard.find_sensitive", boom)
    assert not check_outbound("anything", Vault()).allowed


def test_scrub_removes_values():
    vault = Vault()
    vault.add("CARD", CARD)
    assert CARD not in scrub(f"failed for {CARD} and x@y.test", vault)


def test_guard_malformed_escape_trailing_backslash_does_not_block_a_clean_payload():
    payload = r'{"page_text": "path C:\temp and a stray \q"} ' + "\\"
    assert check_outbound(payload, Vault()).allowed


def test_guard_malformed_escape_still_catches_a_secret_beside_it():
    vault = Vault()
    vault.add("CARD", CARD)
    assert not check_outbound(f"pay with {CARD} " + "\\", vault).allowed
    escaped = CARD.replace("1", r"\u0031")
    assert not check_outbound(f'{{"text": "{escaped}"}} ' + "\\", vault).allowed
