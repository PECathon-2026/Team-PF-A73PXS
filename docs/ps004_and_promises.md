# PS-004 and agreed product promises (verbatim copy)

Source of truth for docs/requirements_matrix.md and docs/promise_report.md.

## Appendix A: PS-004 problem statement (verbatim, binding)

**PS-004 PrivacyLens: Building a Privacy-Preserving AI Browser Agent**

**Background:** AI-powered agents can automate complex tasks such as shopping, filling forms, managing accounts, and navigating websites. However, these agents often send screenshots and webpage data to cloud-based AI models, potentially exposing sensitive information such as Aadhaar numbers, PAN, passwords, OTPs, financial details, API keys, medical records, and personal messages. This creates significant privacy and security risks.

**Your challenge is to build PrivacyLens, a system that enables AI agents to interact with digital interfaces intelligently while preventing sensitive user information from being exposed to external AI models.**

The core principle is: **Compute what is sensitive locally. Reason globally only on sanitized data.**

### Tasks
**A) Sensitive Information Detection.** Build a system that identifies sensitive information using one or more techniques:
- Pattern Detection: Use regular expressions and validation algorithms to detect Aadhaar, PAN, emails, phone numbers, credit/debit cards, passwords, OTPs, API keys, and other sensitive data.
- Structural Analysis: Inspect DOM elements, accessibility trees, metadata, or other interface representations to identify sensitive fields.
- AI-Based Detection: Optionally use OCR, computer vision, face detection, or Named Entity Recognition to identify contextual PII.
- Defense in Depth: Combine multiple techniques to reduce missed detections and false positives.

**B) Privacy-Preserving Sanitization**
- Redact sensitive regions in screenshots using blackout, masking, or other suitable techniques.
- Replace sensitive text with semantic placeholders such as [REDACTED:CARD] or [REDACTED:PASSWORD].
- Preserve non-sensitive information and interface structure required for AI reasoning.
- Ensure that original sensitive values cannot be recovered from the sanitized data sent externally.

**C) AI Reasoning and Automation**
- Integrate an LLM, VLM, or another suitable AI model to reason over sanitized information.
- Enable the AI to understand the interface and perform tasks through suitable interaction mechanisms.
- Validate proposed actions and reject invalid targets or unsafe operations.
- Prevent the model from attempting to infer or reconstruct redacted information.
- Require user approval for sensitive or irreversible actions where appropriate.

**D) Privacy and Security Validation**
- Validate outgoing data before transmission and block requests containing detected, unredacted sensitive information.
- Implement fail-closed behavior when sanitization or validation fails.
- Protect against prompt injection, invalid actions, and accidental data leakage through logs or metadata.
- Provide a before/after privacy preview and an offline or local-only mode where feasible.
- Minimize data retention and clearly define the system's trust boundaries.

### Technical Requirements
Participants are free to choose any technology, architecture, programming language, framework, or tech stack. Building a browser extension is not mandatory. Possible approaches include browser extensions, desktop applications, web applications, middleware, local proxies, AI agent frameworks, or hybrid edge-cloud systems. Teams may use existing tools, libraries, models, and automation frameworks. The choice of technology is open-ended; the solution must demonstrate effective and measurable privacy protection.

### Evaluation Scenarios
Test the solution using controlled webpages or equivalent datasets covering:
1. E-commerce checkout: card details and addresses.
2. Authentication: passwords, emails, and OTPs.
3. Customer support: phone numbers and private messages.
4. Video conferencing: faces and participant information.
5. Developer settings: API keys, tokens, and IP addresses.

Use synthetic sensitive data and annotated test cases to measure system performance.

### Evaluation Criteria
- PII Detection Recall: How much sensitive information is detected?
- Redaction Precision: How accurately is sensitive information identified without excessive redaction?
- Privacy Leakage: Does sensitive information appear in outgoing payloads?
- Context Preservation: Can the AI still understand the interface after sanitization?
- Task Success: Can the system complete its intended task?
- Performance: What are the processing latency and resource requirements?
- Security: How effectively does the system handle adversarial inputs and validation failures?

All reported results must be supported by reproducible tests. Zero leakage claims must be limited to the tested scenarios and transmission pathways.

### Deliverables
- Complete source code and a working demonstration.
- Sensitive-information detection and sanitization pipeline.
- AI reasoning and interaction components.
- Test cases, evaluation scripts, and measured results.
- Setup instructions and configuration files.
- A 2–3 minute demo video showing sensitive-data detection, sanitization, AI task execution, and blocking of an unsafe outgoing payload.

### Documentation (README.md) must include
1. Architecture diagram and data flow.
2. Setup instructions and configuration.
3. Detection and sanitization methodology.
4. AI integration and action validation.
5. Security assumptions and known limitations.
6. Evaluation methodology and reproducible results.

### Bonus Points
- Fully local AI processing without cloud requests.
- Advanced contextual PII detection.
- Adaptive redaction that preserves maximum useful context.
- Protection against prompt injection and adversarial webpages.
- User-defined privacy rules and explainable redaction.
- Local secret injection without exposing values to cloud models.
- Automated leakage testing using synthetic canary values.
- Cross-browser or desktop-agent support.
- Human approval for sensitive actions.

### Expected Outcome
Build a functional system that demonstrates how AI agents can interact with digital interfaces while protecting sensitive user information. The goal is not to build a specific application or use a prescribed tech stack, but to develop an innovative, reliable, and measurable solution to privacy-preserving AI automation.

---

## Appendix B: Product promises our team agreed on (binding)

1. **For everyday people, zero thinking.** The main screen shows only the task box with suggestion chips, the live view, the "See what the AI sees" switch, one status line and one narration line. Nothing else.
2. **Signature switch.** "See what the AI sees" crossfades the live view between the real page and the blacked-out version the AI receives.
3. **Human words only** on the main screen, approval sheet and status details. Technical terms appear only in "How it works".
4. **Apple Pay-style approval sheet** for sensitive or irreversible actions: one plain sentence, a large Approve, a quiet Cancel, "Why am I asked?". It is a bottom sheet on phones and centered on laptops. Routine steps never interrupt.
5. **Automatic light and dark** following the device setting, with no theme switch. Both themes meet 4.5:1 contrast.
6. **Works on phones and laptops,** from 375 px to 1440 px, with touch targets of at least 44 px.
7. **Phone as approval remote:** the same URL on a phone on the same Wi-Fi joins the session, and approvals appear on both devices.
8. **Status line tells the truth:** "N things hidden · nothing private shared", or "Stopped N unsafe message(s)" when the guard blocks.
9. **Visible unsafe-payload block for the demo:** a clearly labelled "Run leak test" button in "How it works" tries to send a planted canary secret, bypassing the sanitizer for that one test request. The guard must block it, and the status line must show it. (The statement's demo video requires showing a blocked unsafe outgoing payload.) Also show the injection page being stopped.
10. **Explainable redaction:** every hidden item has a human reason ("16 digits that pass the card checksum").
11. **User-defined privacy rules** in "How it works": per-type toggles and an "Always hide…" custom rule, which take effect on the next step.
12. **Offline mode works with no internet** (Mock, or Ollama if installed). Gemini is used only when a key is present.
13. **Local secret injection:** the real card and password are typed by the laptop, never seen by the AI.
14. **"How it works" view for judges:** pipeline steps, raw vs outbound payload, validation and approval decisions, eval results, privacy settings and AI choice.
15. **Measured results:** a baseline of N secrets exposed without PrivacyLens vs 0 with it, plus recall, precision, task success, latency, resources, adversarial cases and cross-browser, all from `eval/results.json`.
16. **Natural, explainable code** that passes the section 2 style rules, with a `docs/explain/` page for every module.
17. **Fresh-clone setup works** by following only the README, on Windows and on macOS/Linux.
