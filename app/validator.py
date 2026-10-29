import json
import re
from urllib.parse import urlparse

from app.detectors import find_sensitive
from app.models import Action, SanitizedSnapshot, ValidationResult
from app.vault import TOKEN, Vault

ACTIONS = {"click", "type", "select", "scroll", "wait", "done", "ask_user"}
IRREVERSIBLE = re.compile(r"\b(pay|submit|send|delete|remove|confirm|purchase|place order|transfer|rotate|verify)\b", re.I)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}


def parse_action(raw: str) -> Action | None:
    try:
        data = json.loads(raw)
        return Action(str(data["action"]), str(data.get("target", "")), str(data.get("value", "")),
                      str(data.get("reason", "")))
    except (ValueError, KeyError, TypeError):
        return None


def _leaves_device(text: str) -> bool:
    for url in re.findall(r"(?:https?:)?//[^\s\"']+", text):
        host = urlparse(url if url.startswith("http") else "http:" + url).hostname or ""
        if host not in LOCAL_HOSTS:
            return True
    return False


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
    if _leaves_device(literal):
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
    if action.action == "click":
        if not element.can_click:
            return ValidationResult(False, reason=f"{element.id} cannot be clicked.")
        if element.href and _leaves_device(element.href):
            return ValidationResult(False, reason="That link leaves this device.")
        label = f"{element.label} {element.text}"
        return ValidationResult(True, needs_approval=bool(IRREVERSIBLE.search(label)), reason=label.strip())
    if not (element.can_type or element.tag == "select"):
        return ValidationResult(False, reason=f"{element.id} cannot take text.")
    bad = _check_value(action, snap, vault)
    if bad:
        return bad
    uses_secret = bool(TOKEN.search(action.value))
    return ValidationResult(True, needs_approval=uses_secret and snap.element_types.get(action.target) in
                            {"CARD", "CVV", "PASSWORD", "OTP"}, reason=element.label)
