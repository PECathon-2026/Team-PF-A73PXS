# validator.py

## What it does
Checks every action the AI proposes before anything happens in the browser. It can reject the action, allow it, or allow it only after the user approves.

## How
- `parse_action` turns the reply into an `Action`, or None if it is not valid JSON with an `action` key.
- `validate`:
  - rejects unknown actions; allows scroll, wait, done and ask_user directly,
  - reveal: `_check_reveal` runs (see below),
  - rejects a target id that is not in the sanitized snapshot, or one that is hidden on the page,
  - click: the element must be clickable; a link whose `href` leaves this machine is rejected (`_leaves_device`); labels matching `IRREVERSIBLE` (pay, submit, send, delete, confirm, verify, rotate and others) need approval. `readable` first applies NFKC, removes zero-width characters and maps Greek and Cyrillic lookalike letters to Latin, so "Pay" spelled with a Greek Rho still counts. A submit button with no readable name also needs approval,
  - type/select: the element must accept text, then `_check_value` runs.
- `_check_value` rejects a raw `[REDACTED` placeholder, unknown tokens, tokens whose type differs from the field's `expects` type, literal text containing a non-local URL or a bare host name such as `evil.example/collect`, and literal text in which `find_sensitive` finds any pattern. Types the user shares are not scanned there, so the AI may type a value it was allowed to read (an Aadhaar number into a chat box, for example); a hidden type in literal text is still rejected.
- Typing a token into a CARD, CVV, PASSWORD or OTP field needs approval.
- `_check_reveal` handles `{"action": "reveal", "value": "{{TYPE#n}}"}`. The value must be exactly one token that the vault knows. If that type is `redact` (Hide) the action is rejected with "That kind of data is set to stay hidden." If it is `ask`, the action is allowed with `needs_approval`. If it is already shared (Reveal, or approved earlier in this task) it is allowed without approval.

## Likely judge questions
1. What stops the AI pasting my card into a chat box? The chat box has no CARD type, so `{{CARD#1}}` is rejected as "does not belong in this field". The AI never knows the real number, so it cannot type it literally.
2. What if the AI writes a URL to send data out? Literal values with a non-local URL are rejected, links to other hosts cannot be clicked, and the browser blocks external requests anyway.
3. Is approval based on the button text? Yes, a keyword regex over the label as a person reads it. Lookalike letters, zero-width characters and unnamed submit buttons are handled. A button with an ordinary but misleading name ("Continue" that actually pays) would not ask.
4. What happens after a rejection? The reason goes into history so the AI can correct itself. Three rejections in a row end the run.
5. Can the AI read a hidden value by asking for it? Only for a type on Ask permission, and only after the user says yes. A Hide type is refused here, before the user is asked. An unknown token or a value that is not exactly one token is refused too.
