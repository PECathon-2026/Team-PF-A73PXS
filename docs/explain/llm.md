# llm.py

## What it does
Provides the planners that choose the next action. All of them expose `next_action(system, observation) -> str`, returning a JSON string.

## How
- `GeminiLLM` posts the system prompt and the observation to the Gemini `generateContent` endpoint with `httpx`, asking for JSON at temperature 0. The key comes from `GEMINI_API_KEY` in .env and is sent only in the `x-goog-api-key` header. It tries 3 times, then raises `LLMError`. The model name comes from `GEMINI_MODEL` or a default.
- `MockLLM` is an offline scripted planner. It parses the sanitized observation and follows a fixed plan per task keyword ("pay", "log me in", "support", "mute", "rotate", "feedback"). It fills fields by matching `expects` to a token in `secrets` (`_fill_all`), and skips actions already in history. With `gullible=True` it tries to paste the card token into the feedback box, which simulates an AI that obeyed a prompt injection.
- `RecordingLLM` wraps any provider and stores every payload it was given. The eval uses this to check what would have been sent.
- `get_llm("gemini")` returns Gemini; any other name returns Mock.

## Likely judge questions
1. Is the Gemini call the only network call to the outside? From the Python code, yes. Browser requests to other hosts are blocked by executor.py.
2. Is the payload checked before Gemini sees it? Yes. agent.py calls `check_outbound` on the exact system prompt plus observation before calling `next_action`.
3. Why a Mock? It makes tests and the demo repeatable and offline. It only reads the sanitized observation, the same input Gemini gets.
4. What if Gemini returns garbage? `parse_action` in validator.py returns None, the step is recorded as rejected, and after 3 rejections in a row the run stops.
5. Does it retry on every error? It retries on any HTTP error, including 4xx errors that will not succeed on retry.
