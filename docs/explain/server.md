# server.py

## What it does
A FastAPI app that serves the web UI and the fake scenario pages, and exposes a small JSON API to start runs, watch them, approve steps, edit Privacy choices and see eval results.

## How
- `lifespan` loads `config/rules.json` and launches one headless Chromium for the whole server, with proxy-only WebRTC.
- `State` holds the single current session, the rules and the chosen AI ("gemini" if a key is set, else "mock"). `POST /api/config` accepts only mock, mock_fooled or gemini. `_end_session` cancels the running agent before closing its browser.
- `PORT` comes from `PRIVACYLENS_PORT`, default 8000. The Windows launcher sets it to the first free port from 8000 up.
- Endpoints:
  - `GET /api/scenarios`, `GET/POST /api/config`
  - `POST /api/session` closes any old session, starts a new one and runs `agent.run` in the background. The new session gets the server's rules object, so later saves reach the running task from its next step.
  - `GET /api/session` status, events, report, blackout boxes, the approval (`question`, `why`, `kind`: "share" or "action") and `shared` (`[{"type", "by": "choice" | "approval"}]`)
  - `GET /api/session/inspect` raw page text (first 4000 characters), the outbound payload and history
  - `GET /api/session/image/real` and `/ai` the raw and blacked-out screenshots
  - `POST /api/session/approve`, `POST /api/leak-test` (creates a bare session without a browser if none exists)
  - `GET /api/rules` returns `{"modes", "hints", "custom"}`. `PUT /api/rules` takes any subset of those keys, merges `modes` and `hints`, replaces `custom`, saves to rules.json and returns the same shape.
  - `GET /api/eval`, `POST /api/eval/run` (runs `eval/run_eval.py --quick` with `sys.executable`; one at a time, HTTP 409 if already running)
- `_check_modes` refuses a mode map with an unknown type or a mode other than redact, ask or reveal, and refuses CUSTOM set to anything but redact (HTTP 400: "Always hide rules always stay hidden.").
- `/scenarios` and `/` are static file mounts. Run directly, it listens on `0.0.0.0`.
- `trusted_host` refuses `/api/` requests whose Host header is not localhost or a bare IP address (a DNS rebinding attack needs a host name).
- `local_only` allows only requests from this machine for: changing the AI, starting a session, the raw page text and payload (`inspect`), the real screenshot, the leak test, saving rules and running the eval.
- `_check_pattern` refuses custom rules that are too long, invalid, or slower than 2 s on test strings (checked in a separate process started with `sys.executable`, which can be killed).
- Paths are relative to the folder above `app/`. In the Windows bundle that is the `_internal` folder next to `PrivacyLens.exe`, so rules are saved to `_internal\config\rules.json` there.

## Likely judge questions
1. Why show the raw screenshot and raw text in the UI? So the user can compare what they see with what the AI sees. This is local data shown to the local user.
2. Is the API protected? There is no password. Anyone on the same network can open the UI, see the AI view, status, hidden-item list and approval question, read the rules, and approve or cancel a pending step, including a request to share a kind of data. The raw screenshot, raw text, settings and runs are refused with HTTP 403 unless the request comes from this machine.
3. Can two people approve? `Session.answer` accepts the first answer only.
4. Where is the Gemini key? Read from .env by `load_dotenv`; the API only reports whether it is present. The Windows launcher reads the `.env` next to `PrivacyLens.exe` before the server starts.
5. Why does a helper process work inside the exe? `sys.executable` is `PrivacyLens.exe` there. `packaging/launcher.py` sees a `-c` or `.py` argument and runs it as Python would, so the rule speed check and the quick eval can still start a separate process. Neither was run from the exe in our clean-environment check; that check covered `/api/config`, the page, the default modes and one share run.
