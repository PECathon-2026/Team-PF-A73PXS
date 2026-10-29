from app.detectors import find_sensitive
from app.vault import Vault

MIN_LEN = 4


def scrub(text: str, vault: Vault) -> str:
    """Remove real values from any message before it is logged or shown."""
    for value in sorted(vault.values(), key=len, reverse=True):
        if len(value) >= MIN_LEN:
            text = text.replace(value, "[hidden]")
    for f in reversed(find_sensitive(text)):
        if f.source == "pattern":
            text = text[:f.start] + "[hidden]" + text[f.end:]
    return text
