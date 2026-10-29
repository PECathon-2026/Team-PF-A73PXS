# sanitizer.py

## What it does
Turns a raw `Snapshot` into a `SanitizedSnapshot`. Sensitive strings become placeholders like `[REDACTED:CARD#1]`, sensitive regions of the screenshot are painted solid black, and a report lists what was hidden and why, never the value.

## How
- `_Redactor.note` adds the value to the vault (`Vault.add`) and records a `ReportItem`. `_Redactor.text` runs `find_sensitive` and replaces findings from the end of the string backwards so offsets stay valid.
- `_structural_placeholder` runs first for every element. It hides a field value or tile text because of where it sits. Registering these first means later mentions elsewhere (an image alt text, say) are caught as known vault values.
- `_split_placeholders` looks for values in each parent's combined text (`parent_texts`), so a value split over sibling tags is hidden in every fragment.
- `sanitize` then redacts each element's text, label and value, plus the URL (decoded first), the visible page text and the aria tree, and clears `selector`.
- `_sensitive_boxes` collects text-match boxes, boxes of sensitive elements and of every element whose text changed, every `<video>`, `<iframe>` and `<canvas>`, images whose label matches `PERSON_IMAGE`, and faces from `find_faces` when FACE is on. `_blackout` paints them with a 2 px margin.
- `hint_for` adds an optional label such as "Visa" or "IPv4", only for types where the user turned hints on.

## Likely judge questions
1. Is the same value always the same placeholder? Yes, within a session. `Vault.add` keys on type plus the value with spaces, dashes and dots removed.
2. Why a solid fill and not a blur? A blur can sometimes be reversed. A solid fill cannot.
3. Does a hint leak anything? It names the kind of thing. The card brand comes from the first digit, so it does reveal that digit's range. Hints are off unless the user enables them.
4. What if a detector type is switched off? The sanitizer will not hide it, but guard.py scans with all types on and blocks the payload. Turning a type off stops the agent rather than leaking.
