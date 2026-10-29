# prompts.py

## What it does
Builds the exact text the AI receives: a fixed system prompt and a JSON observation for each step.

## How
- `SYSTEM_PROMPT` tells the model it sees a sanitized page, that `page_text` and `elements` are untrusted content, never to guess hidden values, to fill private fields only with a token from `secrets`, and to reply with one JSON action.
- `build_observation(task, snap, vault, history)` returns JSON with:
  - `task` and `url` (sanitized),
  - `secrets`: the list of `{{TYPE#n}}` tokens and their kind, never values,
  - `elements`: id, tag, label, text, value, `expects` (structural type) and click/type flags, for visible elements only,
  - `page_text`: the sanitized text, cut to 3000 characters,
  - `history`: the last 8 steps.

The aria tree and the screenshot are not part of the observation.

## Likely judge questions
1. Does a system prompt stop prompt injection? No, not on its own. It is one layer. The validator and the approval prompt are the hard checks.
2. Why send hidden page text at all? So the model can see the page fully; it is sanitized first and labelled untrusted. Hidden elements are not offered as targets.
3. What does history contain? Each step's action, element label, value (tokens, not secrets) and result. The label comes from the raw page snapshot, so the guard is what stops a raw sensitive label from going out.
4. Why cut page text to 3000 characters? To bound payload size and cost. Text past that point is not seen by the AI.
