import re

PLACEHOLDER = re.compile(r"\[REDACTED:([A-Z_]+)#(\d+)(?: - [^\]]+)?\]")
TOKEN = re.compile(r"\{\{([A-Z_]+#\d+)\}\}")


def token_type(token: str) -> str:
    """The type part of a token: CARD for CARD#2."""
    return token.split("#")[0]


def _key(value: str) -> str:
    return re.sub(r"[\s\-.]", "", value).lower()


class Vault:
    """Real values for one session. Lives in memory only and is cleared when the session ends."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], str] = {}
        self._by_token: dict[str, str] = {}
        self._counts: dict[str, int] = {}
        self.canaries: set[str] = set()

    def add(self, type_: str, value: str, hint: str = "") -> str:
        """Return the placeholder for a value; the same value always gets the same one."""
        key = (type_, _key(value))
        token = self._by_key.get(key)
        if token is None:
            self._counts[type_] = self._counts.get(type_, 0) + 1
            token = f"{type_}#{self._counts[type_]}"
            self._by_key[key] = token
            self._by_token[token] = value
        suffix = f" - {hint}" if hint else ""
        return f"[REDACTED:{token}{suffix}]"

    def resolve(self, token: str) -> str | None:
        return self._by_token.get(token)

    def items(self) -> list[tuple[str, str, str]]:
        """(type, value, token) for every value that has a placeholder."""
        return [(token_type(t), v, t) for t, v in self._by_token.items()]

    def tokens(self) -> list[str]:
        return list(self._by_token)

    def values(self) -> list[str]:
        """Every real value in raw and compact form, plus canaries, for the outbound guard."""
        raw = list(self._by_token.values()) + list(self.canaries)
        return raw + [_key(v) for v in raw if _key(v) != v]

    def clear(self) -> None:
        self._by_key.clear()
        self._by_token.clear()
        self._counts.clear()
        self.canaries.clear()
