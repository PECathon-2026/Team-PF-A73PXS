# server.py

## What it does
A FastAPI app that serves the web UI and the fake scenario pages, and exposes a small JSON API to start runs, watch them, approve steps, edit rules and see eval results.

## How
- `lifespan` launches one headless Chromium for the whole server.
- `State` holds the single current session, the rules (loaded from config/rules.json) and the chosen AI ("gemini" if a key is set, else "mock").
- Endpoints:
  - `GET /api/scenarios`, `GET/POST /api/config`
  - `POST /api/session` closes any old session, starts a new one and runs `agent.run` in the background
  - `GET /api/session` status, events, report, blackout boxes
  - `GET /api/session/inspect` raw page text (first 4000 characters), the outbound payload and history
  - `GET /api/session/image/real` and `/ai` the raw and blacked-out screenshots
  - `POST /api/session/approve`, `POST /api/leak-test`
  - `GET/PUT /api/rules`, `GET /api/eval`, `POST /api/eval/run` (runs `eval/run_eval.py --quick`)
- `/scenarios` and `/` are static file mounts. Run directly, it listens on `0.0.0.0`.

## Likely judge questions
1. Why show the raw screenshot and raw text in the UI? So the user can compare what they see with what the AI sees. This is local data shown to the local user.
2. Is the API protected? No. There is no authentication. Because it listens on 0.0.0.0, anyone on the same network can open the UI, see the raw screenshot and raw text, approve steps and change rules.
3. Can two people approve? `Session.answer` accepts the first answer only.
4. Where is the Gemini key? Read from .env by `load_dotenv`; the API only reports whether it is present.
