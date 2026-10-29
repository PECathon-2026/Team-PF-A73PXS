import re

from app.detectors import KNOWN_REASON, find_sensitive
from app.vault import Vault

MIN_LEN = 4


def scrub(text: str, vault: Vault) -> str:
    """Remove real values from any message before it is logged or shown."""
    for value in sorted(vault.values(), key=len, reverse=True):
        if len(value) >= MIN_LEN:
            text = re.sub(re.escape(value), "[hidden]", text, flags=re.IGNORECASE)
    # Saved values written with other spacing or case, and anything that looks private.
    for f in reversed(find_sensitive(text, vault=vault)):
        if f.source == "pattern" or f.reason == KNOWN_REASON:
            text = text[:f.start] + "[hidden]" + text[f.end:]
    return text
