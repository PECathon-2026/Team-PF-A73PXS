# wording.py

## What it does
Writes every sentence a person reads during a run: the narration line ("Filling in your card number..."), the approval question for an action, and the approval question for sharing a kind of data. It keeps technical words out of the main screen and the approval sheet.

## How
- `narration(action, kind)` returns "Filling in <field>..." for typing (`HUMAN_FIELD` maps CARD to "your card number" and so on, anything else is "a field"), "Pressing a button..." for a click, and "Looking at the page..." otherwise.
- `action_question(action, label, raw_text, vault, kind)` returns a question and a "why" line for an action that needs approval:
  - Typing a CARD, CVV, PASSWORD or OTP token: `Use your saved <secret word> for "<label>"?` with "It fills in private details that stay on this device."
  - A label with the word "pay": `Pay <amount> with your card ending <last 4>?`. The amount is the first "Rs" or "INR" amount on the raw page; the last 4 digits come from the CARD value in the vault. Why line: "Paying cannot be undone."
  - Any other click: `Go ahead and press "<label>"?` with "This kind of step cannot easily be undone."
  - `TECHNICAL` replaces the words redacted, guard, payload, llm and token in a page label with "item", so a page cannot put those words on the sheet.
- `share_question(kind)` returns `Let the AI read your <name> for this task?` and `SHARE_WHY`: "You chose to be asked before this is shared. It will be shared for this task only." The name comes from `rules.TYPE_NAMES` (AADHAAR is "Aadhaar number").
- agent.py calls `narration` and `action_question` from `_act`, and `share_question` from `_share`. The web UI shows the question and labels the buttons "Allow for this task" and "Do not share" when the approval kind is "share", and "Approve" and "Cancel" otherwise.

## Likely judge questions
1. Why a separate file? These sentences used to sit inside agent.py. Keeping them together makes the human-words promise easy to check in one place, and agent.py stays about control flow.
2. Does the payment question leak the card number? It shows the last 4 digits, in the local UI and on a phone that has joined. It is never sent to the AI. Anyone on the same Wi-Fi who opens the page can also see it (see threat_model.md).
3. Can a page put misleading words in the question? The label is page text, so a page can choose what the button is called. `TECHNICAL` removes technical words; it does not judge whether the label is honest.
4. Is the share question the same for every kind? Yes, only the name changes. The "why" line always says the share is for this task only, which matches `Session.shared_types` being dropped when the task ends.
