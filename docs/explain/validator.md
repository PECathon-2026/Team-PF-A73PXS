# validator.py

## What it does
Checks every action the AI proposes before anything happens in the browser. It can reject the action, allow it, or allow it only after the user approves.

## How
- `parse_action` turns the reply into an `Action`, or None if it is not valid JSON with an `action` key.
- `validate`:
  - rejects unknown actions; allows scroll, wait, done and ask_user directly,
  - rejects a target id that is not in the sanitized snapshot,
  - click: the element must be clickable; a link whose `href` leaves this machine is rejected (`_leaves_device`); labels matching `IRREVERSIBLE` (pay, submit, send, delete, confirm, verify, rotate and others) need approval,
  - type/select: the element must accept text, then `_check_value` runs.
- `_check_value` rejects a raw `[REDACTED` placeholder, unknown tokens, tokens whose type differs from the field's `expects` type, literal text containing a non-local URL, and literal text in which `find_sensitive` finds any pattern.
- Typing a token into a CARD, CVV, PASSWORD or OTP field needs approval.

## Likely judge questions
1. What stops the AI pasting my card into a chat box? The chat box has no CARD type, so `{{CARD#1}}` is rejected as "does not belong in this field". The AI never knows the real number, so it cannot type it literally.
2. What if the AI writes a URL to send data out? Literal values with a non-local URL are rejected, links to other hosts cannot be clicked, and the browser blocks external requests anyway.
3. Is approval based on the button text? Yes, a keyword regex over the sanitized label and text. A button named misleadingly would not trigger it.
4. What happens after a rejection? The reason goes into history so the AI can correct itself. Three rejections in a row end the run.
