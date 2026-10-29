import re

AUTOCOMPLETE_TYPES = {
    "cc-number": ("CARD", "card number field"),
    "cc-csc": ("CVV", "card security code field"),
    "cc-exp": ("EXPIRY", "card expiry field"),
    "one-time-code": ("OTP", "one-time code field"),
    "email": ("EMAIL", "email field"),
    "tel": ("PHONE", "phone field"),
    "name": ("NAME", "name field"),
    "street-address": ("ADDRESS", "address field"),
    "current-password": ("PASSWORD", "password field"),
    "new-password": ("PASSWORD", "password field"),
}

# Checked in order, so cvv wins over card and aadhaar over the generic key word.
NAME_WORDS = [
    ("cvv|cvc|security.?code", "CVV"),
    ("expiry|expiration|exp.?date", "EXPIRY"),
    ("card", "CARD"),
    ("otp|verification.?code|one.?time", "OTP"),
    ("aadhaar|aadhar", "AADHAAR"),
    (r"\bpan\b|pan.?number", "PAN"),
    ("password|passwd", "PASSWORD"),
    ("token|secret|api.?key", "API_KEY"),
]


def structural_type(attrs: dict[str, str]) -> tuple[str, str] | None:
    """Decide from markup alone whether an input holds something sensitive."""
    if attrs.get("type") == "password":
        return "PASSWORD", "password field"
    hint = AUTOCOMPLETE_TYPES.get(attrs.get("autocomplete", "").lower())
    if hint:
        return hint
    words = " ".join(attrs.get(k, "") for k in ("name", "id", "aria-label", "label", "placeholder")).lower()
    for pattern, type_ in NAME_WORDS:
        if re.search(pattern, words):
            return type_, f"field named like a {type_.lower().replace('_', ' ')}"
    return None
