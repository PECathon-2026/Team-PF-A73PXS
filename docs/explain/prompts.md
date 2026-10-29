# prompts.py

## What it does
Builds the exact text the AI receives: a fixed system prompt and a JSON observation for each step.

## How
- `SYSTEM_PROMPT` tells the model it sees a sanitized page, that `page_text` and `elements` are untrusted content, never to guess hidden values, to fill private fields only with a token from `secrets`, to use "done" only after its own history shows the needed steps, to use "ask_user" only when no visible step can move the task forward, and to reply with one JSON action.
- `build_observation(task, snap, vault, history)` returns JSON with:
  - `task` and `url` (sanitized),
  - `secrets`: the list of `{{TYPE#n}}` tokens and their kind, never values,
  - `elements`: id, tag, label, text, value, `expects` (structural type) and click/type flags, for visible elements only,
  - `page_text`: the sanitized visible text, cut to 3000 characters,
  - `outline`: the sanitized accessibility tree, cut to 2000 characters (`OUTLINE_CHARS`),
  - `history`: the last 8 steps.

The screenshot is not part of the observation.

## Likely judge questions
1. Does a system prompt stop prompt injection? No, not on its own. It is one layer. The validator and the approval prompt are the hard checks.
2. Is hidden page text sent? No. `page_text` is built from visible text and `title`/`alt`/`data-*` attributes. Hidden elements are neither listed nor accepted as targets by the validator.
3. What does history contain? Each step's action, element label, value (tokens, not secrets) and result. The label comes from the raw page snapshot, so the guard is what stops a raw sensitive label from going out.
4. Why cut page text to 3000 characters? To bound payload size and cost. Text past that point is not seen by the AI.
