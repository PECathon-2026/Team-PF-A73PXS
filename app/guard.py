import re

from app.detectors import compact, compact_value, find_sensitive, normalize
from app.models import GuardResult
from app.rules import Rules
from app.vault import Vault

SHORT = 6


def decoded(payload: str) -> str:
    """The payload with JSON escapes such as \\n, \\u00a0 or \\u200b turned back into the characters they stand for."""
    return payload.encode("latin-1", "backslashreplace").decode("unicode_escape")


def _contains(value: str, text: str, flat: str) -> bool:
    if len(value) < SHORT:
        # short values such as a CVV would match inside ids and sizes, so require whole-word matches
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])", text) is not None
    needle = compact_value(value)
    return value in text or (len(needle) >= SHORT and needle in flat)


def _leaked_value(texts: list[str], vault: Vault) -> bool:
    for text in texts:
        flat = compact(text)[0]
        if any(value and _contains(value, text, flat) for value in vault.values()):
            return True
    return False


def check_outbound(payload: str, vault: Vault, rules: Rules | None = None) -> GuardResult:
    """Last check before anything leaves the machine. Any failure inside it blocks the payload."""
    try:
        plain = decoded(payload)
        if _leaked_value([normalize(payload)[0], normalize(plain)[0]], vault):
            return GuardResult(False, "a hidden value was about to be sent")
        scan = Rules(custom=rules.custom if rules else [])
        for f in find_sensitive(plain, scan):
            if f.source == "pattern":
                return GuardResult(False, f"unhidden {f.type.lower().replace('_', ' ')} found in the message")
        return GuardResult(True)
    except Exception:
        return GuardResult(False, "the safety check failed, so nothing was sent")
