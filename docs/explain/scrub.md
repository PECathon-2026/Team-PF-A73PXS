# scrub.py

## What it does
Removes real values from any message before it is stored in the audit trail shown in the UI.

## How
`scrub(text, vault)` replaces every vault value of 4 or more characters with `[hidden]`, ignoring case, longest first so a long value is not half replaced by a shorter one. Then it runs `find_sensitive` with the vault and replaces any "pattern" finding and any saved value written with other spacing or case.

`Session.emit` in agent.py passes every audit detail through `scrub`.

## Likely judge questions
1. How is this different from the guard? The guard decides whether a payload may leave. Scrub cleans local log text and never blocks.
2. Why the 4 character minimum? Shorter values (a 3 digit CVV) would wipe digits from unrelated text.
3. Are error messages scrubbed? agent.py never records the exception message, which can quote page data. It records the class name (`step failed safely: ValueError`) and the last three frames as file, line and function name (`_trace_summary`), and that text also goes through scrub.
4. Does it handle a value written with other spacing or case? Yes. The saved-value finder compares letters and digits only, in lower case.
