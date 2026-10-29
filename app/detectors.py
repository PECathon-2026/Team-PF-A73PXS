import ipaddress
import math
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from app.context_rules import find_contextual
from app.models import Finding
from app.rules import Rules
from app.vault import Vault

ZERO_WIDTH = set("​‌‍⁠﻿")
# Any single symbol between digits; the checksums keep dates and amounts from being flagged.
SEP = r"[\W_]"

# Verhoeff, not Luhn: this is how UIDAI computes the Aadhaar check digit
_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def verhoeff_valid(digits: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _entropy(s: str) -> float:
    return -sum(s.count(c) / len(s) * math.log2(s.count(c) / len(s)) for c in set(s))


def _is_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(s)
    except ValueError:
        return False
    return True


def _card_ok(s: str) -> bool:
    d = _digits(s)
    return 13 <= len(d) <= 19 and luhn_valid(d)


def _aadhaar_ok(s: str) -> bool:
    d = _digits(s)
    return len(d) == 12 and d[0] in "23456789" and verhoeff_valid(d)


def _key_ok(s: str) -> bool:
    return _entropy(s) >= 3.5 and any(c.isdigit() for c in s) and any(c.isalpha() for c in s)


@dataclass(frozen=True)
class Pattern:
    type: str
    regex: re.Pattern
    reason: str
    check: Callable[[str], bool] = lambda s: True
    group: int = 0


def _p(type_: str, rx: str, reason: str, check=lambda s: True, group: int = 0):
    return Pattern(type_, re.compile(rx), reason, check, group)


# Order is priority: when two matches overlap, the earlier type wins.
PATTERNS = [
    _p("CARD", rf"(?<!\d)\d(?:{SEP}?\d){{12,18}}(?!\d)", "digits that pass the card checksum", _card_ok),
    _p("AADHAAR", rf"(?<!\d)(?<!\d{SEP})[2-9]\d{{3}}{SEP}?\d{{4}}{SEP}?\d{{4}}(?!\d)(?!{SEP}\d)",
       "digits that pass the Aadhaar checksum", _aadhaar_ok),
    _p("PAN", r"(?<![A-Za-z0-9])[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z](?![A-Za-z0-9])",
       "matches the PAN format with a valid holder-type letter"),
    _p("API_KEY", r"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_\-]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}"
       r"|AIza[0-9A-Za-z_\-]{30,}|xox[bp]-[A-Za-z0-9\-]{10,})", "starts like a known API key or token"),
    _p("API_KEY", r"eyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]+", "has the shape of a JWT"),
    _p("API_KEY", r"(?i)\b(?:api[_ -]?key|token|secret|key)\b[^\w\n]{0,6}([A-Za-z0-9_\-+/=]{24,})",
       "long random string next to the word key, token or secret", _key_ok, 1),
    _p("PASSWORD", r"(?i)\bpass(?:word|code)?\b\s*[:=]\s*(\S+)", "value written after the word password", group=1),
    # Bounded parts and a lookbehind keep a long run of letters from being rescanned at every offset.
    _p("EMAIL", r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]{1,63}(?:\.[A-Za-z0-9\-]{1,63}){1,8}",
       "looks like an email address"),
    _p("EMAIL", r"(?i)(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]{1,64}\s*[\[(]at[\])]\s*[A-Za-z0-9\-]{1,63}"
       r"(?:\s*(?:\.|[\[(]dot[\])])\s*[A-Za-z0-9\-]{1,63}){1,8}", "an email address with at and dot spelled out"),
    _p("UPI", r"(?<![\w.])[\w.\-]{2,}@(?:ok\w+|ybl|paytm|upi|apl|ibl|axl|sbi|axisbank|hdfcbank|icici)\b(?!\.)",
       "looks like a UPI payment address"),
    _p("IFSC", r"(?<![A-Za-z0-9])[A-Z]{4}0[A-Z0-9]{6}(?![A-Za-z0-9])", "matches the IFSC bank code format"),
    _p("IP_ADDRESS", r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!\d)(?!\.\d)", "valid IPv4 address", _is_ip),
    _p("IP_ADDRESS", r"(?<![\w:])[0-9A-Fa-f:]*:[0-9A-Fa-f:]*:[0-9A-Fa-f:]*(?![\w:])", "valid IPv6 address", _is_ip),
    _p("PHONE", rf"(?<!\d)(?<!\d{SEP})(?:\+91{SEP}?|0)?[6-9](?:{SEP}?\d){{9}}(?!\d)(?!{SEP}\d)", "Indian mobile number"),
    _p("PHONE", rf"(?<![\d+])\+\d{{1,3}}{SEP}?\(?\d{{2,4}}\)?{SEP}?\d{{3,4}}{SEP}?\d{{3,4}}(?!\d)",
       "international phone number"),
    _p("CVV", r"(?i)\b(?:cvv2?|cvc2?|security code)\b\D{0,12}?(?<!\d)(\d{3,4})(?!\d)",
       "3 or 4 digits next to the word CVV", group=1),
    _p("OTP", r"(?i)\b(?:otp|one[- ]time|verification code|passcode|code)\b\D{0,30}?(?<!\d)(\d{4,8})(?!\d)",
       "4 to 8 digits next to the word code or OTP", group=1),
]
PRIORITY = {p.type: i for i, p in reversed(list(enumerate(PATTERNS)))}


def normalize(text: str) -> tuple[str, list[int]]:
    """Return NFKC text without zero-width characters, and for each output character
    the offset it came from in the original, so spans can be mapped back."""
    chars: list[str] = []
    origin: list[int] = []
    for i, ch in enumerate(text):
        if ch in ZERO_WIDTH:
            continue
        for c in unicodedata.normalize("NFKC", ch):
            chars.append(c)
            origin.append(i)
    return "".join(chars), origin


def _scan(pattern: Pattern, norm: str, origin: list[int], text: str) -> list[Finding]:
    found = []
    for m in pattern.regex.finditer(norm):
        s, e = m.span(pattern.group)
        if s == e or not pattern.check(m.group(pattern.group)):
            continue
        start, end = origin[s], origin[e - 1] + 1
        n = len(_digits(m.group(pattern.group)))
        reason = f"{n} {pattern.reason}" if pattern.type in ("CARD", "AADHAAR") else pattern.reason
        found.append(Finding(pattern.type, start, end, text[start:end], reason, "pattern"))
    return found


def _resolve_overlaps(findings: list[Finding]) -> list[Finding]:
    ranked = sorted(findings, key=lambda f: (PRIORITY.get(f.type, 99), -(f.end - f.start), f.start))
    kept: list[Finding] = []
    for f in ranked:
        if all(f.end <= k.start or f.start >= k.end for k in kept):
            kept.append(f)
    return sorted(kept, key=lambda f: f.start)


def _custom_findings(text: str, rules: Rules) -> list[Finding]:
    found = []
    for rx in rules.custom:
        for m in re.finditer(rx, text):
            if m.end() > m.start():
                found.append(Finding("CUSTOM", m.start(), m.end(), m.group(), "matches your Always hide rule", "pattern"))
    return found


KNOWN_MIN_LEN = 5
KNOWN_SKIP = {"CVV", "EXPIRY"}
KNOWN_REASON = "a detail you saved earlier"


def compact(text: str) -> tuple[str, list[int]]:
    """Lowercase letters and digits only, with the index each one came from, so spacing,
    punctuation and case cannot hide a saved value."""
    chars: list[str] = []
    origin: list[int] = []
    for i, ch in enumerate(text):
        for c in ch.lower():
            if c.isalnum():
                chars.append(c)
                origin.append(i)
    return "".join(chars), origin


def compact_value(value: str) -> str:
    """The same compact form for a single saved value; zero-width characters are not alphanumeric, so they drop out."""
    return "".join(filter(str.isalnum, unicodedata.normalize("NFKC", value).lower()))


def _known_findings(norm: str, origin: list[int], vault: Vault) -> list[Finding]:
    found = []
    flat, flat_origin = compact(norm)
    known = [(t, v) for t, v, _ in vault.items()] + [("CUSTOM", c) for c in vault.canaries]
    for type_, value in known:
        needle = compact_value(value)
        if len(needle) < KNOWN_MIN_LEN or type_ in KNOWN_SKIP:
            continue
        # No word-boundary check: page text glues neighbouring tags together ("Test User OneNext").
        pos = flat.find(needle)
        while pos >= 0:
            start, end = origin[flat_origin[pos]], origin[flat_origin[pos + len(needle) - 1]] + 1
            found.append(Finding(type_, start, end, value, KNOWN_REASON, "context"))
            pos = flat.find(needle, pos + 1)
    return found


def find_sensitive(text: str, rules: Rules | None = None, vault: Vault | None = None) -> list[Finding]:
    if not text.strip():
        return []
    rules = rules or Rules()
    norm, origin = normalize(text)
    found: list[Finding] = []
    for pattern in PATTERNS:
        if rules.on(pattern.type):
            found += _scan(pattern, norm, origin, text)
    found += [f for f in find_contextual(text) if rules.on(f.type)]
    if rules.on("CUSTOM"):
        found += _custom_findings(text, rules)
    if vault:
        found += _known_findings(norm, origin, vault)
    return _resolve_overlaps(found)
