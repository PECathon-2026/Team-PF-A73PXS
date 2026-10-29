import json
from dataclasses import dataclass, field
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "rules.json"

ALL_TYPES = [
    "CARD", "AADHAAR", "PAN", "EMAIL", "PHONE", "OTP", "PASSWORD", "API_KEY",
    "IP_ADDRESS", "UPI", "IFSC", "CVV", "NAME", "ADDRESS", "DOB", "MEDICAL",
    "ACCOUNT", "EXPIRY", "CUSTOM", "FACE",
]


@dataclass
class Rules:
    enabled: dict[str, bool] = field(default_factory=lambda: {t: True for t in ALL_TYPES})
    hints: dict[str, bool] = field(default_factory=dict)
    custom: list[str] = field(default_factory=list)

    def on(self, type_: str) -> bool:
        return self.enabled.get(type_, True)

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "hints": self.hints, "custom": self.custom}


def load_rules(path: Path = RULES_PATH) -> Rules:
    if not path.exists():
        return Rules()
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = Rules()
    rules.enabled.update(data.get("enabled", {}))
    rules.hints = data.get("hints", {})
    rules.custom = data.get("custom", [])
    return rules


def save_rules(rules: Rules, path: Path = RULES_PATH) -> None:
    path.write_text(json.dumps(rules.to_dict(), indent=2), encoding="utf-8")
