# rules.py

## What it does
Holds the user's privacy settings: which types to hide, which types get a hint label, and custom "Always hide" regexes.

## How
- `ALL_TYPES` lists every type the system knows.
- `Rules` is a dataclass with `enabled` (all on by default), `hints` and `custom`. `on(type_)` returns True for unknown types.
- `load_rules` reads `config/rules.json` if it exists; `save_rules` writes it. The server's `PUT /api/rules` updates and saves.

## Likely judge questions
1. If I turn off CARD, will my card go to the AI? No. The sanitizer stops hiding it, but the guard scans with every type on and blocks the payload, so the run stops.
2. What are custom rules? Regexes from the user. Matches become CUSTOM findings. The guard also uses them.
3. What if a custom regex is invalid? `re.finditer` raises. In the sanitizer the step fails and is blocked; in the guard the exception is caught and the payload is blocked. Either way nothing is sent, but the agent cannot run until the rule is fixed. The server does not check the regex when saving.
4. Why default to on for unknown types? A new type should be hidden until someone decides otherwise.
