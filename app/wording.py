import re

from app.models import Action
from app.rules import TYPE_NAMES
from app.vault import Vault

HUMAN_FIELD = {"CARD": "your card number", "CVV": "the card security code", "EXPIRY": "the card expiry",
               "PASSWORD": "your password", "OTP": "the one-time code", "EMAIL": "your email", "PHONE": "your phone",
               "NAME": "your name", "ADDRESS": "your address"}
TECHNICAL = re.compile(r"redacted|guard|payload|llm|token", re.I)
SECRET_WORDS = {"CARD": "card number", "CVV": "card security code", "PASSWORD": "password", "OTP": "one-time code"}
SHARE_WHY = "You chose to be asked before this is shared. It will be shared for this task only."


def narration(action: Action, kind: str) -> str:
    if action.action == "type":
        return f"Filling in {HUMAN_FIELD.get(kind, 'a field')}..."
    return "Pressing a button..." if action.action == "click" else "Looking at the page..."


def action_question(action: Action, label: str, raw_text: str, vault: Vault, kind: str) -> tuple[str, str]:
    label = TECHNICAL.sub("item", label)
    if kind in SECRET_WORDS and action.action == "type":
        return f"Use your saved {SECRET_WORDS[kind]} for \"{label}\"?", "It fills in private details that stay on this device."
    amount = re.search(r"(?:Rs\.?|INR)\s?[\d,]+", raw_text)
    card = next((v for t, v, _ in vault.items() if t == "CARD"), "")
    if re.search(r"\bpay\b", label, re.I):
        parts = [f"Pay {amount.group()}" if amount else "Pay", f"with your card ending {card[-4:]}" if card else ""]
        return " ".join(p for p in parts if p) + "?", "Paying cannot be undone."
    return f"Go ahead and press \"{label}\"?", "This kind of step cannot easily be undone."


def share_question(kind: str) -> tuple[str, str]:
    return f"Let the AI read your {TYPE_NAMES.get(kind, 'private detail')} for this task?", SHARE_WHY
