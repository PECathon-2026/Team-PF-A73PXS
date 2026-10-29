# scrub.py

## What it does
Removes real values from any message before it is stored in the audit trail shown in the UI.

## How
`scrub(text, vault)` replaces every vault value of 4 or more characters with `[hidden]`, longest first so a long value is not half replaced by a shorter one. Then it runs `find_sensitive` with default rules and replaces any "pattern" finding with `[hidden]`.

`Session.emit` in agent.py passes every audit detail through `scrub`.

## Likely judge questions
1. How is this different from the guard? The guard decides whether a payload may leave. Scrub cleans local log text and never blocks.
2. Why the 4 character minimum? Shorter values (a 3 digit CVV) would wipe digits from unrelated text.
3. Are error messages scrubbed? agent.py only records the exception class name (`step failed safely: ValueError`), not the message, and that string also goes through scrub.
4. Does it handle a value saved with spaces? Yes. `vault.values()` includes compact forms too.
