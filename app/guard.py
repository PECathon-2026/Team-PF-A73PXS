import re

from app.detectors import compact, compact_value, find_sensitive, normalize
from app.models import GuardResult
from app.rules import ALL_TYPES, Rules
from app.vault import Vault

# Three length cut-offs on purpose: below SHORT the guard needs whole-word matches so it does not block ids and
# sizes; scrub.MIN_LEN is lower because a false hit in a log only costs readability; detectors.KNOWN_MIN_LEN sits
# between, because a saved value found in page text is replaced by a placeholder the AI still has to work with.
SHORT = 6
# Pairs are matched left to right, so an escaped backslash is consumed before it can start another escape.
JSON_ESCAPE = re.compile(r'\\(?:u([0-9a-fA-F]{4})|x([0-9a-fA-F]{2})|U([0-9a-fA-F]{8})|(["\\/bfnrt]))')
SIMPLE_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


def _unescape(m: re.Match) -> str:
    code = m[1] or m[2] or m[3]
    return chr(int(code, 16)) if code else SIMPLE_ESCAPES[m[4]]


def decoded(payload: str) -> str:
    """The payload with JSON escapes such as \\n, \\u00a0 or \\u200b turned back into the characters they stand for.
    A malformed escape, such as a trailing backslash, stays as written instead of failing every step."""
    return JSON_ESCAPE.sub(_unescape, payload)


def _contains(value: str, text: str, flat: str) -> bool:
    if len(value) < SHORT:
        # short values such as a CVV would match inside ids and sizes, so require whole-word matches
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])", text) is not None
    needle = compact_value(value)
    return value in text or (len(needle) >= SHORT and needle in flat)


def _leaked_value(texts: list[str], values: list[str]) -> bool:
    for text in texts:
        flat = compact(text)[0]
        if any(value and _contains(value, text, flat) for value in values):
            return True
    return False


def check_outbound(payload: str, vault: Vault, rules: Rules | None = None) -> GuardResult:
    """Last check before anything leaves the machine. Any failure inside it blocks the payload.
    Only kinds of data the user chose to share (mode reveal) may pass; canaries never do."""
    try:
        rules = rules or Rules()
        plain = decoded(payload)
        shared = {t for t in ALL_TYPES if not rules.on(t)}
        if _leaked_value([normalize(payload)[0], normalize(plain)[0]], vault.values(skip_types=shared)):
            return GuardResult(False, "a hidden value was about to be sent")
        # Fresh Rules: hints do not matter here, and shared kinds are left out of the scan rather than
        # filtered afterwards, so a shared match can never win an overlap against a hidden one.
        scan = Rules(custom=rules.custom).with_shared(shared)
        for f in find_sensitive(plain, scan):
            if f.source == "pattern":
                return GuardResult(False, f"unhidden {f.type.lower().replace('_', ' ')} found in the message")
        return GuardResult(True)
    except Exception:
        return GuardResult(False, "the safety check failed, so nothing was sent")
