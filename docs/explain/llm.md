# llm.py

## What it does
Provides the planners that choose the next action. All of them expose `next_action(system, observation) -> str`, returning a JSON string.

## How
- `GeminiLLM` posts the system prompt and the observation to the Gemini `generateContent` endpoint with `httpx`, asking for JSON at temperature 0. The key comes from `GEMINI_API_KEY` in .env and is sent only in the `x-goog-api-key` header. Each request has a 30 s timeout. On a network error, HTTP 429 or 5xx it tries again, up to 3 attempts, waiting 2 s and then 6 s between them (`RETRY_SECONDS` is 2, 6, 15; there is no wait after the last attempt). Then it raises `LLMError`. Other 4xx errors raise `LLMError` at once. The model name comes from `GEMINI_MODEL`, default `gemini-3.5-flash-lite`.
- `MockLLM` is an offline scripted planner. It parses the sanitized observation and follows a fixed plan per task keyword ("pay", "log me in", "support", "mute", "rotate", "feedback"). It fills fields by matching `expects` to a token in `secrets` (`_fill_all`), and skips actions already in history. With `gullible=True` it tries to paste the card token into the feedback box, which simulates an AI that obeyed a prompt injection.
- `RecordingLLM` wraps any provider and stores every payload it was given. The eval uses this to check what would have been sent.
- `get_llm("gemini")` returns Gemini, `get_llm("mock_fooled")` returns the gullible Mock (shown in the UI as "Offline test AI that obeys the page"), any other name returns the normal Mock.

## Likely judge questions
1. Is the Gemini call the only network call to the outside? From the Python code, yes. Browser requests to other hosts are blocked by executor.py.
2. Is the payload checked before Gemini sees it? Yes. agent.py calls `check_outbound` on the exact system prompt plus observation before calling `next_action`.
3. Why a Mock? It makes tests and the demo repeatable and offline. It only reads the sanitized observation, the same input Gemini gets.
4. What if Gemini returns garbage? `parse_action` in validator.py returns None, the step is recorded as rejected, and after 3 rejections in a row the run stops.
5. Does it retry on every error? No. Network errors, 429 and 5xx are retried; other 4xx errors (bad key, bad model name) stop at once.
6. How well does Gemini do? See `gemini.task_success_pct` in eval/results.json: 94.4% over 3 runs per scenario, with 0 leaked values.
