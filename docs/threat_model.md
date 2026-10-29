# Threat model

## Assets
- Saved user details in the vault: card number, CVV, expiry, name, address, phone, email, password (fake data in config/user_profile.fake.json).
- Sensitive values seen on pages: IDs, keys, OTPs, IPs, names, faces and the rest of `ALL_TYPES`.
- The Gemini API key in .env.
- The user's intent: no payment or other irreversible action without consent.
- The user's Privacy choices: no kind of data reaches the AI unless the user set it to Reveal or approved a request for it in the current task.

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
| Injection makes AI paste a secret | Token type must match field type; literal values with patterns, external URLs or bare host names rejected; hidden elements cannot be targets; hidden text is not sent | `validator._check_value`, `validator.validate`, `sanitizer.sanitize` |
| Irreversible actions | User approval for pay/submit/send/verify-style clicks (lookalike letters and zero-width characters folded), unnamed submit buttons, and typing CARD, CVV, PASSWORD, OTP | `validator._click_needs_approval`, `validator.readable`, `agent._act`, `agent.Session.ask` |
| Page exfiltrates via HTTP, WebSocket or WebRTC | Abort every non-local browser request; close every non-local WebSocket (`context.route_web_socket`); remove WebRTC constructors with an init script; proxy-only WebRTC flag on Chromium | `executor.block_external`, `executor.NO_WEBRTC_JS`, `server.lifespan` |
| Someone on the network changes settings or reads raw data | Rules, AI choice, session start, raw text, raw screenshot, leak test and eval run accept only requests from this machine (HTTP 403 otherwise) | `server.local_only` |
| Another web page reads the API through DNS rebinding | `/api/` requests with an unknown Host header get HTTP 403 | `server.trusted_host` |
| Invalid, oversized or slow custom rule | Rejected on save with HTTP 400; speed checked in a separate process with a 2 s limit | `server.put_rules`, `server._check_pattern`, `server._pattern_is_fast` |
| AI asks to read a hidden kind | `reveal` is accepted only for a known token of a kind on Ask permission; Hide kinds are refused; the user must answer "Allow for this task"; no answer in 120 s is no and stops the run | `validator._check_reveal`, `agent._share`, `wording.share_question` |
| An approval outlives its task | Approved kinds live in `Session.shared_types`, in memory only; every task gets a new `Session` with an empty set; approvals are never written to rules.json | `agent.Session`, `agent._step` |
| Sharing one kind opens the door for others | The guard leaves out only the shared kinds, before scanning; every other kind, every canary and every Always hide match still blocks | `guard.check_outbound`, `vault.Vault.values(skip_types)`, `rules.Rules.mode` |
| Always hide rules switched off through the API | `PUT /api/rules` refuses CUSTOM set to anything but redact; `Rules.mode("CUSTOM")` is always redact | `server._check_modes`, `rules.Rules.mode` |
| Agent loops | 12 step budget, 3 rejections in a row stop | `agent.STEP_BUDGET`, `agent.MAX_REJECTIONS` |
| Secrets in logs | Scrub every audit message (saved values matched regardless of spacing and case); exceptions logged by class and file/line only; blocked hosts logged by site only | `scrub.scrub`, `agent.Session.emit`, `agent._trace_summary`, `executor.site_of` |
| API key exposure | Key read from .env, sent only as a request header | `llm.GeminiLLM` |

## Known limitations
- Participant names in a video call are found only by a structural tile rule (`dom_snapshot._structure_of`). Names outside such a container, not introduced with "my name is", and not saved in the vault, are missed.
- Saved values are matched without word boundaries, so a saved value can be found and hidden inside a longer word or number.
- Version strings like 1.2.3.4 are valid IPv4 addresses and are hidden as IP_ADDRESS. Postal codes after the word "code" (for example "code 560001") are hidden as OTP.
- Canaries are caught by exact match or after removing spacing, punctuation, case, zero-width characters and JSON escapes. A base64-encoded, reworded or split canary is not caught by the guard.
- The Haar face detector misses side profiles, small, tilted or covered faces, and can fire on face-like shapes.
- The server listens on 0.0.0.0 with no password. `POST /api/config`, `POST /api/session`, `GET /api/session/inspect`, `GET /api/session/image/real`, `POST /api/leak-test`, `PUT /api/rules` and `POST /api/eval/run` call `local_only` and return 403 to other machines. These stay open to anyone on the same network: `GET /api/session` (status, hidden-item list, events, the approval question with the last 4 card digits), `GET /api/session/image/ai` (the blacked-out screenshot), `GET /api/rules` and `POST /api/session/approve` (approve or cancel the pending step). `GET /api/scenarios`, `GET /api/config` and `GET /api/eval` are also open but hold no page data.
- The Host header check (`server._trusted_host`) accepts `localhost` and any bare IP address, and refuses every other host name. DNS rebinding needs a host name, so this blocks it without depending on which network adapters the PC has. Settings, session start, the leak test, the raw page text and the real screenshot also require the request to come from the computer itself, so open the app on the laptop as http://localhost:8000, not with the LAN address.
- Covered pathways: the AI request payload, and browser network requests (HTTP through `context.route`, WebSockets through `context.route_web_socket`, WebRTC removed from pages). Channels outside the browser context are not covered. No eval scenario attempts an external request, so this pathway is proven by code and tests, not by a measured attack.
- Approval for typing a secret is remembered per field-type group for the session (card and CVV share one group). Irreversible clicks ask every time.
- The click approval trigger is a keyword match on the button label as a person reads it (lookalike letters and zero-width characters folded; unnamed submit buttons ask). A button with an ordinary but misleading name, such as "Continue" that pays, would not ask.
- A page can label a free-text box as a card field; the validator would then allow a CARD token there. Approval is the remaining check.
- A short saved value such as a CVV that appears as a whole word elsewhere makes the guard block the step (a false block, not a leak).
- Custom rules are checked on save (`put_rules` returns 400 for an invalid pattern, one longer than 100 characters, or one slower than 2 s on test strings). A rules.json edited by hand is not checked this way.
- The model receives text only. The blacked-out screenshot is shown to the user, not sent.

### Privacy choices (reveal and ask)
- A kind set to Reveal, or approved in the current task, reaches the AI by design. For that kind the sanitizer does not hide it and the guard does not block it. This is the user's decision, confirmed in the UI, and not a leak in our terms; but the 0-leak numbers in eval/results.json were measured with the default settings (every kind on Ask, nothing approved) and do not describe a setup where the user reveals something.
- The exemption is per kind, not per value. Approving AADHAAR lets every Aadhaar number on the page through for the rest of the task, including one that is not the user's.
- A share approval can come from any device on the same network, like any other approval (`POST /api/session/approve` is open). Someone on the Wi-Fi who opens the page while a share request is waiting can allow it.
- Changing Privacy choices (`PUT /api/rules`) is limited to this machine, and the "Privacy choices" link is hidden unless the page is opened as localhost. `GET /api/rules` is open to the network, so others can read the choices.
- A choice saved during a run applies from the next step of that run, not only from the next run.
- Hint switches are no longer in the UI; hints can be set only in rules.json or through `PUT /api/rules`.
- The `reveal` action and the new system prompt were tested with the Mock planner only. Gemini has not been run with them.

### Windows bundle
- `PrivacyLens.exe` runs any `-c <code>` or `.py` argument as Python (`packaging/launcher.py`), because the app starts helper processes with `sys.executable`. Anyone who can start programs as this user can already run code, so this adds no new access, but the exe should be treated like a Python interpreter.
- The exe is not signed. Windows SmartScreen will likely warn on first start.
- No key is shipped. The user puts their own `.env` next to the exe. It holds the Gemini key in plain text, like the `.env` of a source install.
- Rule changes are written inside the bundle folder (`_internal\config\rules.json`). Replacing the folder with a new version loses them and resets every kind to the default.
- Detection is regex, checksum and keyword based. It covers the tested scenarios; see eval/results.json for measured recall and precision.
