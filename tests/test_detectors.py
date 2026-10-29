import pytest

from app.detectors import find_sensitive, luhn_valid, normalize, verhoeff_valid
from app.rules import Rules


def types(text: str, rules: Rules | None = None) -> list[str]:
    return [f.type for f in find_sensitive(text, rules)]


def test_luhn():
    assert luhn_valid("4111111111111111")
    assert not luhn_valid("4111111111111112")


def test_verhoeff():
    assert verhoeff_valid("2363")
    assert not verhoeff_valid("2364")


@pytest.mark.parametrize("text", [
    "card 4111 1111 1111 1111",
    "card 4111-1111-1111-1111",
    "card 4111111111111111",
    "card 4111.1111.1111.1111",
    "card 4​111 1111 1111 1111",
    "card ４１１１ 1111 1111 1111",
    "card 4111 1111\n1111 1111",
])
def test_card_obfuscations(text):
    assert types(text) == ["CARD"]


def test_card_span_maps_back_to_original():
    text = "pay 4​111 1111 1111 1111 now"
    f = find_sensitive(text)[0]
    assert text[f.start:f.end] == "4​111 1111 1111 1111"


def test_tracking_number_failing_luhn_is_not_a_card():
    assert "CARD" not in types("Tracking 4111 1111 1111 1112")


def test_aadhaar_with_valid_check_digit():
    valid = _aadhaar_with_check("23456789012")
    spaced = f"{valid[:4]} {valid[4:8]} {valid[8:]}"
    assert types(f"id {spaced}") == ["AADHAAR"]


def test_order_id_failing_verhoeff_is_not_aadhaar():
    bad = next(n for n in range(234567890120, 234567890200) if not verhoeff_valid(str(n)))
    assert "AADHAAR" not in types(f"Order {bad}")


def test_pan():
    assert types("PAN ABCPE1234F") == ["PAN"]
    assert types("SKU ABCXE1234F") == []


@pytest.mark.parametrize("text,kind", [
    ("mail me at test.user@example.test", "EMAIL"),
    ("call +91 98765 43210", "PHONE"),
    ("call 9876543210", "PHONE"),
    ("call +1 415 555 0132", "PHONE"),
    ("pay user@okaxis", "UPI"),
    ("branch HDFC0001234", "IFSC"),
    ("server 203.0.113.42", "IP_ADDRESS"),
    ("server 2001:db8::1", "IP_ADDRESS"),
    ("key sk-test-FAKEKEY0123456789abcdefghijklmn", "API_KEY"),
    ("AKIAFAKEFAKEFAKE1234", "API_KEY"),
    ("password: hunter2!", "PASSWORD"),
    ("Your verification code is 482916", "OTP"),
    ("cvv 123", "CVV"),
])
def test_each_type(text, kind):
    assert kind in types(text)


@pytest.mark.parametrize("text", [
    "Invoice total 1,499.00 on 2026-10-29",
    "version 1.2.3 released",
    "time 10:30:45",
    "call 1234567890",
    "SKU 123456",
    "Order code 12",
])
def test_lookalikes_are_not_flagged(text):
    assert types(text) == []


def test_otp_only_near_keyword():
    assert types("room 482916") == []


def test_context_rules():
    assert "NAME" in types("hello, my name is Test User One")
    assert "MEDICAL" in types("my diagnosis is type 2 diabetes")
    assert "DOB" in types("DOB: 01/02/1990")
    assert "ADDRESS" in types("address: 12 Fake Street, Nowhere Town")


def test_rules_can_reveal_a_type_and_add_custom():
    shared = Rules().with_shared({"EMAIL"})
    assert types("a@b.test", shared) == []
    custom = Rules(custom=[r"Project Falcon"])
    assert types("about Project Falcon", custom) == ["CUSTOM"]


def test_custom_rules_stay_hidden_even_if_custom_is_marked_reveal():
    from app.guard import check_outbound
    from app.vault import Vault

    rules = Rules(custom=[r"Project Falcon"]).with_shared({"CUSTOM"})
    assert types("about Project Falcon", rules) == ["CUSTOM"]
    assert not check_outbound("about Project Falcon", Vault(), rules).allowed


def test_normalize_drops_zero_width():
    norm, origin = normalize("a​b")
    assert norm == "ab" and origin == [0, 2]


def _aadhaar_with_check(first11: str) -> str:
    for d in "0123456789":
        if verhoeff_valid(first11 + d):
            return first11 + d
    raise AssertionError
