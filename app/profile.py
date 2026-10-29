import json
from pathlib import Path

from app.vault import Vault

ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / "config" / "user_profile.fake.json"
ANNOTATIONS_PATH = ROOT / "scenarios" / "annotations.json"


def load_profile_into_vault(vault: Vault, path: Path = PROFILE_PATH) -> None:
    """Put the user's saved details in the vault so the agent can refer to them by token only."""
    p = json.loads(path.read_text(encoding="utf-8"))
    card = p.get("card", {})
    saved = [
        ("CARD", card.get("number")), ("CVV", card.get("cvv")), ("EXPIRY", card.get("expiry")),
        ("NAME", card.get("name")), ("ADDRESS", p.get("address")), ("PHONE", p.get("phone")),
        ("EMAIL", p.get("email")), ("PASSWORD", p.get("password")),
    ]
    for type_, value in saved:
        if value:
            vault.add(type_, value)


def load_canaries_into_vault(vault: Vault, path: Path = ANNOTATIONS_PATH) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    for scenario in data["scenarios"].values():
        vault.canaries.update(scenario.get("canaries", []))
