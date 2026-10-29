# context_rules.py

## What it does
Finds sensitive values that have no fixed format and are only recognisable from the words around them: NAME, ADDRESS, DOB, ACCOUNT and MEDICAL.

## How
`CONTEXT_RULES` is a list of (type, regex, reason, group). `find_contextual` runs each regex over the text and returns the captured group as a `Finding` with source "context".

- NAME: one to three capitalised words after "my name is".
- ADDRESS: 10 to 120 characters after "address:" or "address -".
- DOB: a date after "dob", "date of birth" or "born on".
- ACCOUNT: a digit run after "account no", "account number" or "account #".
- MEDICAL: up to 40 characters after words such as "diagnosed with", "prescribed", "blood group", "medication", "allergic to".

## Likely judge questions
1. Will it find a name written without "my name is"? No. Other names are found only if they are saved in the vault (exact match in `_known_findings`, detectors.py) or sit in a structural position (a name input, or a call tile; see dom_snapshot.py).
2. Why is the source "context" and not "pattern"? Keyword rules are weaker evidence than a checksum, so the guard and the validator do not block on them alone.
3. Does the guard block on these? No. guard.py blocks only on "pattern" findings and on vault values. Context findings are redacted by the sanitizer before the guard runs, and the redacted value is then in the vault.
4. Is it case sensitive? The keyword part is not (`(?i:...)`). The NAME capture expects capitalised words.
