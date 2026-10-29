# Judge Q and A

Thirty hard questions we expect, with answers we can back with code. File and function names point to where the answer lives. Numbers come from eval/results.json; the JSON key is given next to each one.

## Privacy and principle

**1. What does "compute locally, reason globally" mean in your code?**
Detection, the vault, the guard and the executor all run on this machine. Only the string built by `prompts.build_observation` from sanitized data goes to the AI, and only after `guard.check_outbound` allows it (`agent._step`).

**2. What exactly leaves the machine?**
One text payload per step: the system prompt plus a JSON observation (task, visible elements, sanitized visible page text, sanitized accessibility outline, history, and a list of secret tokens with their kind). Real values appear only as `{{TYPE#n}}` tokens. The sanitized screenshot is produced but is not sent; the observation is text only today.

**3. Where are the real values kept, and for how long?**
In `vault.Vault`, a Python object in memory. It is filled from `config/user_profile.fake.json` and from values found on pages. `Session.close` calls `vault.clear()`. Nothing is written to disk. All profile data is synthetic.

**4. Can the AI provider learn anything sensitive?**
It sees the page structure, non-sensitive text, field kinds and token names such as `CARD#1`. It does not see values that the detectors find or that sit in the vault. If a detector misses a value that is not in the vault, that value would be sent. Our measured recall is in the results table below; it covers our annotated scenarios only.

## Detection

**5. How do you detect sensitive data?**
Several layers: regex plus checksums in `detectors.find_sensitive` (Luhn for cards, formats for PAN, Aadhaar, phone, email, IP, API keys), keyword context in `context_rules.find_contextual` (OTP near "code", password in a sentence), structural rules in `structure.structural_type` and `dom_snapshot._structure_of` (field types, video tiles), and saved vault values matched regardless of spacing, punctuation, case and zero-width characters. Faces in the screenshot use a Haar detector in `faces.find_faces`.

**6. How do you handle obfuscation like zero-width characters or full-width digits?**
`detectors.normalize` folds them before matching. The adversarial cases "card with zero-width characters", "card in full-width digits", "card split over lines", and the dot, dash and space variants all pass in eval/results.json (`security.cases`).

**7. Why not use an ML NER model?**
Time, size and explainability. Regex, checksum and keyword rules run in a few milliseconds (`performance.detect.median_ms`), need no download, and a judge can read every rule. The cost is that names in free text are only found in limited cases (see limitations).

**8. What about false positives?**
We measured precision on 44 lookalike strings (`detection.lookalikes_checked`), with 0 wrongly hidden (`detection.lookalikes_wrongly_hidden`). Known false positives remain: version strings like 1.2.3.4 are hidden as IP addresses, postal codes after the word "code" ("code 560001") are hidden as OTP, and a saved value can be hidden inside a longer word.

## Sanitization, validator and guard

**9. Why do you need a guard if the sanitizer already removes secrets?**
Defence in depth. The sanitizer can have a bug or a miss. `guard.check_outbound` decodes JSON escapes, then scans the exact outbound string for every vault value (raw, and in a compact form with spacing, punctuation, case and zero-width characters removed), every canary, and any pattern detector hit. Any hit, or any exception inside the guard, blocks the step. It fails closed.

**10. What does the validator check?**
`validator.validate` rejects unknown actions, missing or hidden targets, clicks on non-clickable elements, links that leave the device, `[REDACTED...]` placeholders pasted as text, unknown tokens, tokens whose type does not match the field type (a CARD token in a feedback box), literal values that point to non-local URLs or bare host names, and literal values that match a pattern detector (a guessed card number). `agent._check` rejects "done" before any step has succeeded. It also flags irreversible steps for approval.

**11. What needs user approval?**
Clicks whose label, after folding lookalike letters and zero-width characters, matches pay, submit, send, delete, remove, confirm, purchase, place order, transfer, rotate or verify; submit buttons with no readable name; and typing a CARD, CVV, PASSWORD or OTP token. Typing approval is remembered per field group for the session (card and CVV share one group). Clicks ask every time.

**12. What stops the agent from looping forever?**
`agent.STEP_BUDGET` is 12 steps and `agent.MAX_REJECTIONS` stops after 3 rejected actions in a row. An approval request times out after 120 seconds and counts as "no".

## Prompt injection

**13. What does your injection scenario contain?**
`scenarios/06_injection.html` hides instructions three ways: a `display:none` block, an off-screen `aria-hidden` block, and tiny text. They ask the agent to paste the card, CVV, password, email and phone into the feedback box and send data to an external URL.

**14. How do you prove the agent does not follow it?**
The eval runs a deliberately gullible Mock (`MockLLM(gullible=True)`, in the UI "Offline test AI that obeys the page") that tries to paste the card token into the feedback box. The validator rejects it because the token type does not match the field. Results: `security.injection.card_pasted_into_feedback` is false and `security.injection.attempts_rejected_by_validator` is 3.

**15. Do you strip injection text before it reaches the model?**
Partly. Text hidden from the user (display:none, off-screen, aria-hidden, tiny) is not sent, because the observation uses visible text only and hidden elements are left out. We do not try to detect injection by wording. We assume the model may be fooled and make that harmless: it never holds real secrets, the validator blocks wrong-field tokens and off-site values, the browser blocks external requests, and irreversible steps need approval.

**16. Where does that defence end?**
If a page labels a free-text box as a card field, the validator would allow a CARD token there. Approval is the remaining check. The click approval trigger is a keyword match on the button label, so a button with an ordinary but misleading name ("Continue" that pays) would not ask.

## Local secret injection

**17. How does the agent fill in a card number it never saw?**
The AI replies with, for example, `{"action": "type", "target": "e4", "value": "{{CARD#1}}"}`. After validation and approval, `executor.fill_value` swaps the token for the real value from the vault right before `page.fill`. That function is the only place real values are put back.

**18. Could the real value leak back through history?**
History stores the action value as the AI wrote it, which is the token, not the real value. The next observation is built from it and also passes the guard.

## Network and trust boundaries

**19. What are your trust boundaries?**
Five, listed in docs/threat_model.md: page to agent (page is untrusted), agent to AI service, AI service to agent (reply is untrusted), browser to network, and the local UI and API to the network.

**20. Can a malicious page send data out by itself?**
`executor.block_external` routes every HTTP request and WebSocket of the browser context. Only localhost and data, blob and about URLs continue. Everything else is aborted and only the site name is logged. WebRTC constructors are removed from every page by an init script. `tasks.scenarios.*.blocked_requests` shows 0 for every scenario in the current run, so the scenario pages did not try. This covers Playwright-routed traffic only.

**21. What happens to the Gemini API key?**
It is read from `.env` by `llm.GeminiLLM` and sent only as the `x-goog-api-key` header. It is not logged. Audit messages go through `scrub.scrub`, and exceptions are logged by class name and file/line location, never by message.

## Canaries and leak test

**22. What are canaries?**
Fake marker strings listed per scenario in `scenarios/annotations.json`. They are loaded into the vault as canaries. If one ever shows up in an outbound payload, the guard blocks it, and the eval counts it as a leak.

**23. What does the "Run leak test" button actually do?**
`agent.leak_test` puts a canary in a separate probe vault and passes a payload that contains it straight to `check_outbound`, skipping the sanitizer. It reports whether the guard blocked it. It tests the guard, not the whole pipeline. The full-pipeline version is in the eval: a raw, unsanitized page is fed to the guard and must be blocked (`security.raw_page_blocked_by_guard` is true).

**24. Can a canary get past the guard?**
Yes, if it is encoded, reworded or split. The guard matches exactly, or after removing spacing, punctuation, case, zero-width characters and JSON escapes. Base64 or a split across fields is not caught.

## Providers and design choices

**25. Why no LangChain or an agent framework?**
The loop is about 200 lines in `app/agent.py`. We need to show judges exactly where data crosses the boundary, and one framework layer between our guard and the HTTP call would make that harder to prove. It is also not in our allowed dependency list.

**26. Why both a Mock and Gemini?**
The Mock (`llm.MockLLM`) is a scripted planner that reads only the sanitized observation. It makes tests and the eval repeatable, free and offline, and lets us play a gullible model on purpose. Gemini is the real model for the demo. Measured: `gemini.task_success_pct` is 94.4 (17 of 18 runs) over 3 runs per scenario with `gemini-3.5-flash-lite`, and `gemini.leaked_values_in_ai_payloads` is 0. The one failure was a developer run where the AI could not be reached (a service error).

**27. What happens offline?**
With no key, the server starts in Mock mode and every scenario runs fully offline. If Gemini is selected and the network drops, `GeminiLLM` makes up to 3 attempts with 2 s and 6 s waits and then raises `LLMError`. The run stops with "the AI could not be reached". Nothing is sent anywhere else. Ollama is not implemented.

## Demo server

**28. Your server listens on 0.0.0.0. Is that safe?**
It is there so a phone on the same Wi-Fi can watch and approve. There is no password. `server.local_only` limits changing the AI provider, starting sessions, the raw page text, the raw screenshot, the leak test, saving rules and running the eval to the machine itself, and `server.trusted_host` refuses `/api/` requests whose Host header is not localhost or a bare IP address. Still open to anyone on the network: viewing status, the blacked-out view, the hidden-item list and the approval question, reading the rules, and approving or cancelling a pending step. With fake data this is fine for a demo. It is not fine for real use.

## Evaluation honesty

**29. How did you measure, and what do the numbers not prove?**
`eval/run_eval.py` loads each scenario in Chromium, compares sanitized output against the annotated values in `scenarios/annotations.json`, records every payload given to the AI with `RecordingLLM`, and searches those payloads for every secret. The baseline counts how many annotated values would be in the payload with sanitization switched off. Limits: we wrote both the scenarios and the annotations, so 100% recall means "on our own test set". Task success is 100.0% with the Mock and 94.4% with Gemini over 3 runs per scenario. Cross-browser evidence is Chromium and WebKit only; Firefox could not be launched on our machine (`BrowserType.launch: spawn UNKNOWN`), recorded as `cross_browser.firefox.skipped`. The live server itself always uses Chromium.

**30. What would you fix next?**
Send the blacked-out screenshot to the model (today it is produced and shown in the UI but the observation is text only). Add authentication to the server. Add a local model option such as Ollama. Measure face blackout. Get Firefox running.

## Numbers we quote

Refresh this table from eval/results.json after every eval run.

| Measure | Value | JSON key |
|---|---|---|
| Recall, overall | 100.0% | `detection.recall_overall_pct` |
| Annotated values checked | 29 | `detection.items_checked` |
| Precision | 100.0% | `detection.precision_pct` |
| Lookalikes checked | 44 | `detection.lookalikes_checked` |
| Lookalikes wrongly hidden | 0 | `detection.lookalikes_wrongly_hidden` |
| Exposed without PrivacyLens | 29 | `detection.baseline.secrets_exposed_without_privacylens` |
| Exposed with PrivacyLens | 0 | `detection.baseline.secrets_exposed_with` |
| Task success (Mock) | 100.0% | `tasks.task_success_pct` |
| Leaked values in AI payloads | 0 | `tasks.leaked_values_in_ai_payloads` |
| Card pasted into feedback | false | `security.injection.card_pasted_into_feedback` |
| Injection attempts rejected | 3 | `security.injection.attempts_rejected_by_validator` |
| Adversarial cases passed | 20 of 20 | `security.passed`, `security.total` |
| Raw page blocked by guard | true | `security.raw_page_blocked_by_guard` |
| Full step latency, median / p95 | 1035.9 / 1172.6 ms | `performance.full_step.median_ms`, `.p95_ms` |
| Guard latency, median | 99.4 ms | `performance.guard.median_ms` |
| Peak Python memory | 13.5 MB | `resources.peak_python_mb` |
| Chromium task success / leaks | 100.0% / 0 | `cross_browser.chromium` |
| WebKit task success / leaks | 100.0% / 0 | `cross_browser.webkit` |
| Firefox | skipped | `cross_browser.firefox.skipped` |
| Gemini task success | 94.4% (3 runs per scenario) | `gemini.task_success_pct`, `gemini.runs_per_scenario` |
| Gemini leaked values | 0 | `gemini.leaked_values_in_ai_payloads` |
