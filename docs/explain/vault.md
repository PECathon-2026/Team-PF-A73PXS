# vault.py

## What it does
Holds the real values for one session in memory and hands out placeholders. It is the only map from a `{{TYPE#n}}` token back to a real value.

## How
- `Vault.add(type_, value, hint)` returns `[REDACTED:TYPE#n]` or `[REDACTED:TYPE#n - hint]`. The key is (type, value without spaces, dashes and dots, lower case), so "4111 1111" and "41111111" share a token.
- `resolve(token)` returns the real value or None. `token_type(token)` reads the type from the token name (CARD for CARD#2).
- `items()` and `tokens()` list what is stored.
- `values(skip_types)` returns every raw value and its compact form, plus the canaries, for the guard. Values whose type is in `skip_types` are left out; the guard passes the types the user shares. Canaries are never left out.
- `canaries` is a set of planted test strings loaded by profile.py. They never get placeholders; they exist so the guard can prove it catches them.
- `clear()` empties everything. `Session.close` calls it.
- `PLACEHOLDER` and `TOKEN` are the regexes for `[REDACTED:...]` and `{{...}}`.

## Likely judge questions
1. Is the vault written to disk? No. It is plain dictionaries in the server process.
2. Why does the AI see tokens instead of values? It needs a handle to say "put the card here" without knowing the card. The executor swaps the token for the value at typing time.
3. Could the AI use a token it was not given? The validator rejects unknown tokens and tokens whose type does not match the field.
4. What happens on a crash? The memory goes with the process. The profile file on disk holds fake data only.
5. Does sharing a kind remove its values from the vault? No. They stay, so the executor can still type them. Only the guard's list skips them, and only while that kind is shared.
