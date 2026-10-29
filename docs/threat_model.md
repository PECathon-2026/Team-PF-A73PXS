# Threat model

## Assets
- Saved user details in the vault: card number, CVV, expiry, name, address, phone, email, password (fake data in config/user_profile.fake.json).
- Sensitive values seen on pages: IDs, keys, OTPs, IPs, names, faces and the rest of `ALL_TYPES`.
- The Gemini API key in .env.
- The user's intent: no payment or other irreversible action without consent.

## Trust boundaries
1. Page to agent: page content is untrusted input.
2. Agent to AI service: the outbound payload crosses the network.
3. AI service to agent: the reply is untrusted.
4. Browser to network: requests made by page code.
5. UI and API to the network: the local server.

## Attackers
- Malicious page: hidden prompt injection, tries to make the agent paste secrets into a form or link, or sends requests to its own server.
- Curious or compromised AI provider: reads everything it receives.
- Manipulated or wrong model output: proposes harmful actions.
- Someone on the same network as the machine running the server.

## Mitigations mapped to code

| Threat | Mitigation | Code |
|---|---|---|
| Secrets in the AI payload | Detect and replace with placeholders | `detectors.find_sensitive`, `context_rules.find_contextual`, `structure.structural_type`, `sanitizer.sanitize` |
| Sanitizer miss or bug | Final check on the exact outbound string, fail closed | `guard.check_outbound`, `agent._step`, `agent.run` |
| Secrets in the screenshot | Solid blackout of text boxes, sensitive fields, videos, person images, faces | `dom_snapshot._text_range_boxes`, `sanitizer._sensitive_boxes`, `faces.find_faces` |
| AI needs a secret to fill a form | Tokens only; real value swapped in locally | `vault.Vault`, `executor.fill_value` |
| Injection makes AI paste a secret | Token type must match field type; literal values with patterns or external URLs rejected | `validator._check_value` |
| Irreversible actions | User approval for pay/submit/send/verify-style clicks and for typing CARD, CVV, PASSWORD, OTP | `validator.validate`, `agent._act`, `agent.Session.ask` |
| Page exfiltrates via HTTP or WebSocket | Abort every non-local browser request; close every non-local WebSocket (`context.route_web_socket`) | `executor.block_external` |
| Someone on the network changes settings | Rules, AI choice, session start, leak test and eval run accept only requests from this machine (HTTP 403 otherwise) | `server.local_only` |
| Invalid or oversized custom rule | Rejected on save with HTTP 400 | `server.put_rules`, `server._check_pattern` |
| Agent loops | 12 step budget, 3 rejections in a row stop | `agent.STEP_BUDGET`, `agent.MAX_REJECTIONS` |
| Secrets in logs | Scrub every audit message; only exception class names logged | `scrub.scrub`, `agent.Session.emit` |
| API key exposure | Key read from .env, sent only as a request header | `llm.GeminiLLM` |

## Known limitations
- Participant names in a video call are found only by a structural tile rule (`dom_snapshot._structure_of`). Names outside such a container, not introduced with "my name is", and not saved in the vault, are missed.
- Text split across elements (for example `<b>4111</b> 1111 ...`) is not blacked out on the screenshot, because boxes are computed per text node.
- Version strings like 1.2.3.4 are valid IPv4 addresses and are hidden as IP_ADDRESS. Postal codes after the word "code" can be hidden as OTP.
- Canaries are caught by exact (or space/dash/dot-insensitive) match. An encoded, reworded or split canary is not caught by the guard.
- The Haar face detector misses side profiles, small, tilted or covered faces, and can fire on face-like shapes.
- The server listens on 0.0.0.0 with no authentication. `POST /api/config`, `POST /api/session`, `POST /api/leak-test`, `PUT /api/rules` and `POST /api/eval/run` call `local_only` and return 403 to other hosts. These stay open to anyone on the same network: `GET /api/session` (status, hidden items, events), `GET /api/session/inspect` (raw page text, outbound payload, history), `GET /api/session/image/{kind}` (including the raw screenshot `real`), `GET /api/rules` and `POST /api/session/approve` (approve or cancel the pending step). `GET /api/scenarios`, `GET /api/config` and `GET /api/eval` are also open but hold no page data.
- Only three pathways are covered: the AI request payload, browser HTTP requests through `context.route`, and browser WebSockets through `context.route_web_socket`. Other channels (for example WebRTC) are not routed.
- Approval is remembered per field-type group for the session. Clicks on buttons have no type, so after the user approves one irreversible click, later irreversible clicks in that session run without asking.
- The approval trigger is a keyword match on the button label. A misleadingly named button would not ask.
- A page can label a free-text box as a card field; the validator would then allow a CARD token there. Approval is the remaining check.
- A short saved value such as a CVV that appears as a whole word elsewhere makes the guard block the step (a false block, not a leak).
- Custom rules are checked on save (`put_rules` returns 400 for an invalid pattern or one longer than 100 characters). A rules.json edited by hand is not checked this way.
- Detection is regex, checksum and keyword based. It covers the tested scenarios; see eval/results.json for measured recall and precision.
