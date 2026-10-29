# rules.py

## What it does
Holds the user's Privacy choices: for each kind of private data, one of three modes; which kinds get a hint label; and the user's own "Always hide" regexes.

## How
- `ALL_TYPES` lists every type the system knows. `TYPE_NAMES` gives each one a plain name for questions ("Aadhaar number", "card number").
- `MODES` is `redact`, `ask`, `reveal`. `DEFAULT_MODE` is `ask`.
  - `redact` (shown as Hide): hidden, and the AI cannot ask for it.
  - `ask` (shown as Ask permission, the default for every type): hidden, but the AI may send a `reveal` action for it; the user is asked, and a yes counts for that task only.
  - `reveal` (shown as Reveal): the AI sees the real value.
- `Rules` is a dataclass with `modes` (every type set to `ask`), `hints` and `custom`.
  - `mode(type_)` returns the saved mode, `ask` for an unknown type, and always `redact` for CUSTOM: the user's own Always hide rules can never be revealed.
  - `on(type_)` is True when the type is hidden from the AI, that is, its mode is not `reveal`. Detectors, sanitizer and guard all ask this.
  - `with_shared(types)` returns a copy with those types set to `reveal`. agent.py uses it each step for the kinds the user approved during the current task. The saved rules are not changed.
  - `to_dict` returns `{"modes": {...every type...}, "hints": {...}, "custom": [...]}`.
- `load_rules` reads `config/rules.json`. Unknown types and bad modes are dropped, so those kinds keep `ask`. An old `enabled` key from earlier versions is ignored. `save_rules` writes the same format. The server's `PUT /api/rules` checks, merges and saves.

## Likely judge questions
1. Why is Ask the default and not Hide? With Hide the AI cannot finish a task that really needs an ID. With Ask it still sees nothing until the user agrees, once, for one task. Nothing is shared without a yes.
2. If I set CARD to Reveal, will my card go to the AI? Yes, by design. The sanitizer stops hiding card numbers and the guard stops blocking them. Every other type, the canaries and the Always hide rules stay blocked. The Reveal button asks for confirmation first.
3. Is any type locked? Only CUSTOM. The server refuses any mode other than `redact` for it (HTTP 400), and `mode("CUSTOM")` returns `redact` whatever the file says.
4. What are custom rules? Regexes from the user. Matches become CUSTOM findings, and the guard always uses them.
5. What if a custom regex is invalid or slow? `PUT /api/rules` refuses it with HTTP 400: longer than 100 characters, does not compile, or does not finish on test strings within 2 s in a separate process. A rules.json edited by hand skips that check; then a bad regex makes the step fail and nothing is sent.
6. Why does an unknown type read as `ask`? A new type should be hidden until someone decides otherwise.
