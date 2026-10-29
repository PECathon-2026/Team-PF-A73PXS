# runner.py

## What it does
Runs one scenario end to end without the UI. Used by the eval script.

## How
- `task_for(scenario)` reads the task sentence for a scenario from `scenarios/annotations.json`.
- `run_scenario(browser, base_url, scenario, rules, llm_name, llm, approve)` creates a `Session`, optionally swaps in a given planner (wrapped in `RecordingLLM`), starts it, runs `agent.run` as a task, and answers each approval prompt with `approve` while it waits. With `approve=None` it never answers, so prompts time out as a refusal.

## Likely judge questions
1. Does the eval use the same code path as the UI? Yes. It creates the same `Session` and calls the same `agent.run`.
2. Who approves in the eval? `run_scenario` does, automatically, default yes.
3. How does the eval know what was sent? `RecordingLLM.payloads` keeps every payload, and the eval searches them for annotated values and canaries. See eval/results.json.
4. Can it run with Gemini? Yes, with `llm_name="gemini"` and a key in .env.
