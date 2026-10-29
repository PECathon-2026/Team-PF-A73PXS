import re

from app.detectors import find_sensitive, normalize
from app.models import GuardResult
from app.rules import Rules
from app.vault import Vault

SHORT = 6


def _compact(text: str) -> str:
    return re.sub(r"[\s\-.]", "", text).lower()


def _contains(value: str, text: str, compact: str) -> bool:
    if len(value) < SHORT:
        # short values such as a CVV would match inside ids and sizes, so require whole-word matches
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])", text) is not None
    return value in text or _compact(value) in compact


def check_outbound(payload: str, vault: Vault, rules: Rules | None = None) -> GuardResult:
    """Last check before anything leaves the machine. Any failure inside it blocks the payload."""
    try:
        text, _ = normalize(payload)
        compact = _compact(text)
        for value in vault.values():
            if value and _contains(value, text, compact):
                return GuardResult(False, "a hidden value was about to be sent")
        scan = Rules(custom=rules.custom if rules else [])
        for f in find_sensitive(payload, scan):
            if f.source == "pattern":
                return GuardResult(False, f"unhidden {f.type.lower().replace('_', ' ')} found in the message")
        return GuardResult(True)
    except Exception:
        return GuardResult(False, "the safety check failed, so nothing was sent")
