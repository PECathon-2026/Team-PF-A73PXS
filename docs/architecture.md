# Architecture

PrivacyLens is a browser agent that computes what is sensitive on this machine and sends the AI only a sanitized view of the page. Real values stay in a memory-only vault and are typed into the page locally.

## Data flow

```mermaid
flowchart LR
  subgraph Local["This machine (trusted)"]
    subgraph Browser["Headless Chromium"]
      Page[Scenario page]
      Route[block_external: HTTP and WebSocket routes, WebRTC removed]
    end
    Snap[take_snapshot] --> San[sanitize]
    San --> Obs[build_observation]
    Obs --> Guard{check_outbound}
    Vault[(Vault, memory only)]
    San -. adds values .-> Vault
    Guard -. reads values .-> Vault
    Val{validate} --> Appr{user approval}
    Appr --> Exec[execute and fill_value]
    Exec -. resolves tokens .-> Vault
    Exec --> Page
    Page --> Snap
    Page -->|every request| Route
    UI[Web UI and API on port 8000]
  end
  subgraph Remote["Outside (untrusted)"]
    Gemini[Gemini API]
    Other[Any other host]
  end
  Guard -->|pathway 1: AI request payload| Gemini
  Gemini -->|JSON action| Val
  Route -->|pathway 2: browser requests, aborted| Other
  Route -->|localhost only| Local
```

## Trust boundaries
- Page content is untrusted, even though it is shown in a local browser. It may contain hidden instructions or try to send data out.
- The AI service is outside. It receives only what passes `check_outbound`, and its replies are untrusted until `validate` accepts them.
- The vault, the raw snapshot and the executor are trusted and local.
- The web UI and API are local, but the server listens on 0.0.0.0 with no password so a phone can join. Settings, runs, the raw view and the leak test accept only requests from this machine; a Host header check refuses DNS rebinding (see threat_model.md).

## The two covered transmission pathways
1. AI request payload. Built by `build_observation` from sanitized data only. `agent._step` runs `check_outbound` on the exact string (system prompt plus observation) before `LLM.next_action`. Any finding, vault value, canary or exception blocks the step.
2. Browser network requests. `block_external` routes every HTTP request and every WebSocket of the browser context. Only localhost and data/blob/about URLs continue; everything else is aborted and only the site name is logged. WebRTC, which Playwright cannot route, is removed from every page by an init script, and Chromium runs with proxy-only WebRTC.

Leakage claims cover these two pathways and the tested scenarios only. See eval/results.json.

## One step
1. `take_snapshot` reads elements (with a hidden flag), full and visible text, parent texts, aria tree, screenshot and sensitive text boxes.
2. `sanitize` replaces sensitive strings with `[REDACTED:TYPE#n]` (including values split over sibling tags), keeps only visible text, and blacks out the screenshot.
3. `build_observation` creates the JSON the AI sees (visible elements, sanitized page text and outline, history); secrets appear only as `{{TYPE#n}}` tokens. The screenshot is not sent.
4. `check_outbound` allows or blocks.
5. The AI replies with one JSON action.
6. `validate` checks target (exists, visible), field type, token use and literal values, and flags irreversible steps. `agent._check` also rejects "done" before any step succeeded.
7. The user approves if needed.
8. `execute` acts; `fill_value` puts real values in at this point only.

## Module map
See docs/explain/ for one page per module.
