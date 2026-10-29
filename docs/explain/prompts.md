# prompts.py

## What it does
Builds the exact text the AI receives: a fixed system prompt and a JSON observation for each step.

## How
- `SYSTEM_PROMPT` tells the model it sees a sanitized page, that `page_text`, `outline` and `elements` are untrusted content, never to guess hidden values, to fill private fields only with a token from `secrets`, to use the `reveal` action only for a kind listed in `ask_kinds` that the task needs (and otherwise never to ask for it), to use "done" only after its own history shows the needed steps, to use "ask_user" only when no visible step can move the task forward, and to reply with one JSON action.
- `build_observation(task, snap, vault, history, rules)` returns JSON with:
  - `task` and `url` (sanitized),
  - `secrets`: the list of `{{TYPE#n}}` tokens and their kind, never values,
  - `ask_kinds`: sorted kinds that are in Ask mode for this step and have a token in `secrets`. Kinds already shared in this task are not listed, because agent.py passes `rules.with_shared(shared_types)`. Without `rules` the list is empty,
  - `elements`: id, tag, label, text, value, `expects` (structural type) and click/type flags, for visible elements only,
  - `page_text`: the sanitized visible text, cut to 3000 characters,
  - `outline`: the sanitized accessibility tree without attribute lines or form-field values, cut to 2000 characters (`OUTLINE_CHARS`),
  - `history`: the last 8 steps.

The screenshot is not part of the observation.

## Likely judge questions
1. Does a system prompt stop prompt injection? No, not on its own. It is one layer. The validator and the approval prompt are the hard checks.
2. Is hidden page text sent? No. `page_text` is built from visible text and `title`/`alt`/`data-*` attributes. Hidden elements are neither listed nor accepted as targets by the validator.
3. What does history contain? Each step's action, element label, value (tokens, not secrets) and result. A reveal step stores the token it asked for. The label comes from the raw page snapshot, so the guard is what stops a raw sensitive label from going out.
4. Why cut page text to 3000 characters? To bound payload size and cost. Text past that point is not seen by the AI.
5. Why tell the AI which kinds it may ask for? So it does not ask for Hide kinds or for kinds it already has. The validator enforces the same rule, so a model that ignores the list is still refused.
6. Was Gemini tested with this prompt? Not yet. The reveal rule and `ask_kinds` were added after the last Gemini run, and the free daily quota was used up. The Mock planner was tested with it.
