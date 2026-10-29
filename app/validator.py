import json
import re
import unicodedata
from urllib.parse import urlparse

from app.detectors import ZERO_WIDTH, find_sensitive
from app.models import Action, Element, SanitizedSnapshot, ValidationResult
from app.vault import TOKEN, Vault

ACTIONS = {"click", "type", "select", "scroll", "wait", "done", "ask_user"}
IRREVERSIBLE = re.compile(r"\b(pay|submit|send|delete|remove|confirm|purchase|place\s+order|transfer|rotate|verify)\b",
                          re.I)
# Greek and Cyrillic letters that look like Latin ones, so a Greek Rho in "Pay" still reads as "Pay".
CONFUSABLES = str.maketrans("ΑΒΕΖΗΙΚΜΝΟΡΤΥΧαορυν" "АВЕКМНОРСТУХаеорсухѕіјԁ",
                            "ABEZHIKMNOPTYXaopuv" "ABEKMHOPCTYXaeopcyxsijd")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}
BARE_HOST = re.compile(r"(?<![\w@.\-])((?:[a-z0-9\-]+\.)+[a-z]{2,})(?=/|$)", re.I | re.M)


def parse_action(raw: str) -> Action | None:
    try:
        data = json.loads(raw)
        return Action(str(data["action"]), str(data.get("target", "")), str(data.get("value", "")),
                      str(data.get("reason", "")))
    except (ValueError, KeyError, TypeError, RecursionError):
        return None


def _leaves_device(text: str) -> bool:
    for url in re.findall(r"(?:https?:)?//[^\s\"']+", text):
        host = urlparse(url if url.startswith("http") else "http:" + url).hostname or ""
        if host not in LOCAL_HOSTS:
            return True
    return False


def _names_a_host(text: str) -> bool:
    """Typed text such as 'evil.example/collect' points off the device even without a scheme."""
    return _leaves_device(text) or any(host.lower() not in LOCAL_HOSTS for host in BARE_HOST.findall(text))


def readable(label: str) -> str:
    """The label as a person reads it: no zero-width tricks, no lookalike letters, no odd spaces."""
    text = "".join(c for c in unicodedata.normalize("NFKC", label) if c not in ZERO_WIDTH)
    return text.translate(CONFUSABLES)


def _click_needs_approval(element: Element) -> bool:
    label = readable(f"{element.label} {element.text}")
    if IRREVERSIBLE.search(label):
        return True
    # A submit button with no readable name could be the pay button, so the user decides.
    return element.is_submit and not any(c.isalnum() for c in label)


def _check_value(action: Action, snap: SanitizedSnapshot, vault: Vault) -> ValidationResult | None:
    if "[REDACTED" in action.value:
        return ValidationResult(False, reason="Use a {{TYPE#n}} token from the secrets list, not a placeholder.")
    kind = snap.element_types.get(action.target, "")
    for token in TOKEN.findall(action.value):
        if vault.resolve(token) is None:
            return ValidationResult(False, reason=f"{token} is not a known secret.")
        if vault.type_of(token) != kind:
            return ValidationResult(False, reason=f"{token} does not belong in this field.")
    literal = TOKEN.sub("", action.value)
    if _names_a_host(literal):
        return ValidationResult(False, reason="The value points outside this device.")
    if any(f.source == "pattern" for f in find_sensitive(literal)):
        return ValidationResult(False, reason="The value looks like private data the AI should not know.")
    return None


def validate(action: Action, snap: SanitizedSnapshot, vault: Vault) -> ValidationResult:
    if action.action not in ACTIONS:
        return ValidationResult(False, reason=f"Unknown action '{action.action}'.")
    if action.action in {"scroll", "wait", "done", "ask_user"}:
        return ValidationResult(True)
    element = next((e for e in snap.elements if e.id == action.target), None)
    if element is None:
        return ValidationResult(False, reason=f"No element {action.target or '(none)'} on the page.")
    if element.hidden:
        return ValidationResult(False, reason=f"{element.id} is not visible on the page.")
    if action.action == "click":
        if not element.can_click:
            return ValidationResult(False, reason=f"{element.id} cannot be clicked.")
        if element.href and _leaves_device(element.href):
            return ValidationResult(False, reason="That link leaves this device.")
        return ValidationResult(True, needs_approval=_click_needs_approval(element),
                                reason=f"{element.label} {element.text}".strip())
    if not (element.can_type or element.tag == "select"):
        return ValidationResult(False, reason=f"{element.id} cannot take text.")
    bad = _check_value(action, snap, vault)
    if bad:
        return bad
    uses_secret = bool(TOKEN.search(action.value))
    return ValidationResult(True, needs_approval=uses_secret and snap.element_types.get(action.target) in
                            {"CARD", "CVV", "PASSWORD", "OTP"}, reason=element.label)
