import json
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "rules.json"

ALL_TYPES = [
    "CARD", "AADHAAR", "PAN", "EMAIL", "PHONE", "OTP", "PASSWORD", "API_KEY",
    "IP_ADDRESS", "UPI", "IFSC", "CVV", "NAME", "ADDRESS", "DOB", "MEDICAL",
    "ACCOUNT", "EXPIRY", "CUSTOM", "FACE",
]
MODES = ("redact", "ask", "reveal")
DEFAULT_MODE = "ask"
TYPE_NAMES = {
    "CARD": "card number", "AADHAAR": "Aadhaar number", "PAN": "PAN", "EMAIL": "email address",
    "PHONE": "phone number", "OTP": "one-time code", "PASSWORD": "password", "API_KEY": "API key",
    "IP_ADDRESS": "IP address", "UPI": "UPI address", "IFSC": "bank IFSC code", "CVV": "card security code",
    "NAME": "name", "ADDRESS": "address", "DOB": "date of birth", "MEDICAL": "health details",
    "ACCOUNT": "account number", "EXPIRY": "card expiry", "CUSTOM": "Always hide matches", "FACE": "face",
}


@dataclass
class Rules:
    modes: dict[str, str] = field(default_factory=lambda: {t: DEFAULT_MODE for t in ALL_TYPES})
    hints: dict[str, bool] = field(default_factory=dict)
    custom: list[str] = field(default_factory=list)

    def mode(self, type_: str) -> str:
        # Always hide rules are a list the user wrote on purpose, so no mode can reveal them.
        if type_ == "CUSTOM":
            return "redact"
        return self.modes.get(type_, DEFAULT_MODE)

    def on(self, type_: str) -> bool:
        """True when this kind of data is hidden from the AI."""
        return self.mode(type_) != "reveal"

    def with_shared(self, types: Iterable[str]) -> "Rules":
        """A copy in which the given types are revealed, for one step of a task."""
        return replace(self, modes={**self.modes, **{t: "reveal" for t in types}}, hints=dict(self.hints),
                       custom=list(self.custom))

    def to_dict(self) -> dict:
        return {"modes": {t: self.mode(t) for t in ALL_TYPES}, "hints": self.hints, "custom": self.custom}


def is_mode_map(value) -> bool:
    return isinstance(value, dict) and all(t in ALL_TYPES and m in MODES for t, m in value.items())


def load_rules(path: Path = RULES_PATH) -> Rules:
    """Read saved rules. Unknown types and bad modes are dropped, so those kinds keep the default mode."""
    if not path.exists():
        return Rules()
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = Rules()
    modes = data.get("modes", {})
    if isinstance(modes, dict):
        rules.modes.update({t: m for t, m in modes.items() if is_mode_map({t: m})})
    rules.hints = data.get("hints", {})
    rules.custom = data.get("custom", [])
    return rules


def save_rules(rules: Rules, path: Path = RULES_PATH) -> None:
    path.write_text(json.dumps(rules.to_dict(), indent=2), encoding="utf-8")
