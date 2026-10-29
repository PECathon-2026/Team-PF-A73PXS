import json

from app.models import SanitizedSnapshot
from app.prompts import OUTLINE_CHARS, build_observation
from app.vault import Vault

ARIA = '- textbox "CVV":\n  - /placeholder: "000"\n- link "Help":\n  - /url: /help\n- button "Pay"'


def observe(aria: str) -> dict:
    snap = SanitizedSnapshot("http://127.0.0.1/x", [], "page", aria, b"", [])
    return json.loads(build_observation("Pay", snap, Vault(), []))


def test_outline_carries_the_tree_without_attribute_lines():
    outline = observe(ARIA)["outline"]
    assert 'textbox "CVV"' in outline and 'button "Pay"' in outline
    assert "/placeholder" not in outline and "/url" not in outline


def test_outline_drops_typed_field_values():
    aria = ('- textbox "CVV": "000"\n- textbox "Name on: card" [disabled]: Test User\n'
            '- textbox "Expiry":\n  - /placeholder: MM/YY\n  - text: 01/30\n- text: Total')
    outline = observe(aria)["outline"]
    assert "000" not in outline and "Test User" not in outline and "01/30" not in outline
    assert 'textbox "Name on: card" [disabled]' in outline and 'textbox "Expiry"' in outline
    assert outline.endswith("- text: Total")


def test_outline_is_truncated():
    assert len(observe("- text: x\n" * 1000)["outline"]) == OUTLINE_CHARS
