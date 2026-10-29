# llm.py

## What it does
Provides the planners that choose the next action. All of them expose `next_action(system, observation) -> str`, returning a JSON string.

## How
- `GeminiLLM` posts the system prompt and the observation to the Gemini `generateContent` endpoint with `httpx`, asking for JSON at temperature 0. The key comes from `GEMINI_API_KEY` in .env and is sent only in the `x-goog-api-key` header. The main model comes from `GEMINI_MODEL`, default `gemini-3.5-flash-lite`.
- Fallback models: `GEMINI_FALLBACK_MODELS` is a comma-separated list, default `gemini-3.6-flash,gemini-3.5-flash`; set it to an empty value to turn fallback off. A model that is also the main model is tried once, not twice. Each model has its own free-tier rate limit, so when the main model answers 429 the next model usually still answers. `model_used` records which model wrote each answer, and agent.py writes it into the audit log.
- Retries: `next_action` runs up to 3 rounds. Each round tries the main model first, then each fallback. A network error or timeout (30 s per request), HTTP 429, HTTP 5xx, or an answer with no text (empty candidates, a blocked prompt) moves on to the next model. After a round where every model failed it waits 2 s, then 6 s (`RETRY_SECONDS`), or longer when the service asked for it through a `Retry-After` header or the `retryDelay` in the 429 body, plus up to 1 s of random jitter. A requested wait over 30 s (`MAX_WAIT_SECONDS`) means a used-up daily quota, so that model sits out the rest of the run instead; when no model is left it raises `LLMError` at once. After the last round it raises `LLMError`. Any other 4xx on the main model (bad key, bad request) raises `LLMError` at once; on a fallback it drops that model for the rest of the run.
- `reply_text` joins the answer's text parts, leaving out thought parts, and `first_json_object` returns the first JSON object in it, so a reply wrapped in a code fence or a sentence still parses. Text with no JSON object is passed on unchanged, and the validator rejects it.
- `MockLLM` is an offline scripted planner. It parses the sanitized observation and follows a fixed plan per task keyword ("pay", "log me in", "support", "mute", "rotate", "feedback"). It fills fields by matching `expects` to a token in `secrets` (`_fill_all`), and skips actions already in history. With `gullible=True` it tries to paste the card token into the feedback box, which simulates an AI that obeyed a prompt injection.
- `RecordingLLM` wraps any provider and stores every payload it was given. The eval uses this to check what would have been sent.
- `get_llm("gemini")` returns Gemini, `get_llm("mock_fooled")` returns the gullible Mock (shown in the UI as "Offline test AI that obeys the page"), any other name returns the normal Mock.

## Likely judge questions
1. Is the Gemini call the only network call to the outside? From the Python code, yes. Browser requests to other hosts are blocked by executor.py.
2. Is the payload checked before Gemini sees it? Yes. agent.py calls `check_outbound` on the exact system prompt plus observation before calling `next_action`.
3. Why a Mock? It makes tests and the demo repeatable and offline. It only reads the sanitized observation, the same input Gemini gets.
4. What if Gemini returns garbage? `parse_action` in validator.py returns None, the step is recorded as rejected, and after 3 rejections in a row the run stops.
5. Does it retry on every error? No. Network errors, timeouts, 429, 5xx and empty answers are retried, first on the fallback models; other 4xx errors on the main model (bad key, bad model name) stop at once.
6. Does a fallback model see anything different? No. Every model gets the same payload, which already passed `check_outbound`. Only the model name in the URL changes.
7. How well does Gemini do? See `gemini.task_success_pct` in eval/results.json: 94.4% over 3 runs per scenario, with 0 leaked values. That run predates the fallback models.
