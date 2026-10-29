# server.py

## What it does
A FastAPI app that serves the web UI and the fake scenario pages, and exposes a small JSON API to start runs, watch them, approve steps, edit rules and see eval results.

## How
- `lifespan` launches one headless Chromium for the whole server, with proxy-only WebRTC.
- `State` holds the single current session, the rules (loaded from config/rules.json at startup) and the chosen AI ("gemini" if a key is set, else "mock"). `POST /api/config` accepts only mock, mock_fooled or gemini. `_end_session` cancels the running agent before closing its browser.
- Endpoints:
  - `GET /api/scenarios`, `GET/POST /api/config`
  - `POST /api/session` closes any old session, starts a new one and runs `agent.run` in the background
  - `GET /api/session` status, events, report, blackout boxes
  - `GET /api/session/inspect` raw page text (first 4000 characters), the outbound payload and history
  - `GET /api/session/image/real` and `/ai` the raw and blacked-out screenshots
  - `POST /api/session/approve`, `POST /api/leak-test` (creates a bare session without a browser if none exists)
  - `GET/PUT /api/rules`, `GET /api/eval`, `POST /api/eval/run` (runs `eval/run_eval.py --quick`; one at a time, HTTP 409 if already running)
- `/scenarios` and `/` are static file mounts. Run directly, it listens on `0.0.0.0`.
- `trusted_host` refuses `/api/` requests whose Host header is not localhost or a bare IP address (a DNS rebinding attack needs a host name).
- `local_only` allows only requests from this machine for: changing the AI, starting a session, the raw page text and payload (`inspect`), the real screenshot, the leak test, saving rules and running the eval.
- `_check_pattern` refuses custom rules that are too long, invalid, or slower than 2 s on test strings (checked in a separate process that can be killed).

## Likely judge questions
1. Why show the raw screenshot and raw text in the UI? So the user can compare what they see with what the AI sees. This is local data shown to the local user.
2. Is the API protected? There is no password. Anyone on the same network can open the UI, see the AI view, status, hidden-item list and approval question, read the rules, and approve or cancel a pending step. The raw screenshot, raw text, settings and runs are refused with HTTP 403 unless the request comes from this machine.
3. Can two people approve? `Session.answer` accepts the first answer only.
4. Where is the Gemini key? Read from .env by `load_dotenv`; the API only reports whether it is present.
