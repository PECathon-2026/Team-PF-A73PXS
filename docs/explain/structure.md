# structure.py

## What it does
Decides from the HTML markup alone whether an input field holds something sensitive. This catches values that have no recognisable format, such as a password.

## How
`structural_type(attrs)` checks, in order:
1. `autocomplete` against `AUTOCOMPLETE_TYPES` (cc-number, cc-csc, cc-exp, one-time-code, email, tel, name, street-address, cc-name, current-password, new-password).
2. `type="password"`.
3. `type="email"` or `type="tel"` (`INPUT_TYPES`).
4. Words in name, id, aria-label, label and placeholder against `NAME_WORDS` (cvv, expiry, card, otp, aadhaar, pan, password, token/secret/api key). Order matters: "card cvv" gives CVV, not CARD.

It returns (type, reason) or None.

## Likely judge questions
1. Why not just scan the field value? An empty field has no value, but the agent still needs to know what it expects so it can use the right token. A password also has no pattern.
2. Where is the result used? dom_snapshot.py stores it as `Element.sensitive_type`. The sanitizer hides the value, prompts.py sends the type as `expects`, and the validator checks tokens against it.
3. Can a page lie about its fields? Yes. A free-text box labelled "card" would accept a CARD token. The user approval prompt for CARD, CVV, PASSWORD and OTP is the remaining check.
4. What does it miss? Fields with no helpful attributes. Their values are still scanned by the text detectors.
