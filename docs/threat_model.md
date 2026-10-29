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
| Page exfiltrates via HTTP | Abort every non-local browser request | `executor.block_external` |
| Agent loops | 12 step budget, 3 rejections in a row stop | `agent.STEP_BUDGET`, `agent.MAX_REJECTIONS` |
| Secrets in logs | Scrub every audit message; only exception class names logged | `scrub.scrub`, `agent.Session.emit` |
| API key exposure | Key read from .env, sent only as a request header | `llm.GeminiLLM` |

## Known limitations
- Participant names in a video call are found only by a structural tile rule (`dom_snapshot._structure_of`). Names outside such a container, not introduced with "my name is", and not saved in the vault, are missed.
- Text split across elements (for example `<b>4111</b> 1111 ...`) is not blacked out on the screenshot, because boxes are computed per text node.
- Version strings like 1.2.3.4 are valid IPv4 addresses and are hidden as IP_ADDRESS. Postal codes after the word "code" can be hidden as OTP.
- Canaries are caught by exact (or space/dash/dot-insensitive) match. An encoded, reworded or split canary is not caught by the guard.
- The Haar face detector misses side profiles, small, tilted or covered faces, and can fire on face-like shapes.
- The server listens on 0.0.0.0 with no authentication. Anyone on the same network can view the raw screenshot (`/api/session/image/real`) and the raw page text (`/api/session/inspect`), approve steps, change or disable rules, switch the AI provider and start eval runs.
- Only two pathways are covered: the AI request payload and browser HTTP requests through Playwright routing. WebSocket traffic from the page is not routed by `context.route`.
- Approval is remembered per field-type group for the session. Clicks on buttons have no type, so after the user approves one irreversible click, later irreversible clicks in that session run without asking.
- The approval trigger is a keyword match on the button label. A misleadingly named button would not ask.
- A page can label a free-text box as a card field; the validator would then allow a CARD token there. Approval is the remaining check.
- A short saved value such as a CVV that appears as a whole word elsewhere makes the guard block the step (a false block, not a leak).
- An invalid custom regex blocks every step until fixed; the server does not validate rules on save.
- Detection is regex, checksum and keyword based. It covers the tested scenarios; see eval/results.json for measured recall and precision.
