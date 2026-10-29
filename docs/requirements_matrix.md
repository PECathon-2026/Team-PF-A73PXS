# Requirements matrix

Every row is one bullet from docs/ps004_and_promises.md, copied verbatim. Appendix A is the PS-004 problem statement; Appendix B is our 17 product promises.

Evidence rules:
- Tests are listed by name from `python -m pytest --collect-only -q` (174 tests collected).
- Numbers are only those in eval/results.json, cited by key.
- Screenshots are in docs/screens/.

Status: DONE means code and proof both exist. PARTIAL means some of it is missing or unverified. NOT VERIFIED means it exists but nobody has run the check yet. NOT DONE means it does not exist yet.

## Task A: Sensitive Information Detection

| ID | Requirement (verbatim) | Implemented in | Proof | Status | Note |
|---|---|---|---|---|---|
| A1 | Pattern Detection: Use regular expressions and validation algorithms to detect Aadhaar, PAN, emails, phone numbers, credit/debit cards, passwords, OTPs, API keys, and other sensitive data. | app/detectors.py `find_sensitive`, `luhn_valid`, `verhoeff_valid` | tests/test_detectors.py::test_each_type, test_lookalikes_are_not_flagged, test_otp_only_near_keyword; `detection.recall_overall_pct` | DONE | |
| A2 | Structural Analysis: Inspect DOM elements, accessibility trees, metadata, or other interface representations to identify sensitive fields. | app/structure.py `structural_type`; app/dom_snapshot.py `take_snapshot`, `_structure_of`; app/sanitizer.py `_structural_placeholder` | tests/test_agent_mock.py::test_each_secret_goes_into_its_own_field; tests/test_no_leak.py::test_no_annotated_value_reaches_the_ai | DONE | |
| A3 | AI-Based Detection: Optionally use OCR, computer vision, face detection, or Named Entity Recognition to identify contextual PII. | app/faces.py `find_faces` (Haar face detector); app/context_rules.py `find_contextual` (keyword context, not NER) | tests/test_guard.py::test_screenshot_is_blacked_out; tests/test_detectors.py::test_context_rules | PARTIAL | Face detection exists but has no recall number in eval/results.json; contextual PII uses keyword rules, not an NER model. |
| A4 | Defense in Depth: Combine multiple techniques to reduce missed detections and false positives. | app/detectors.py `find_sensitive` (patterns, checksums, custom rules, vault values) + structure + context rules + app/guard.py `check_outbound` | `detection.precision_pct`, `detection.lookalikes_wrongly_hidden`; tests/test_guard.py::test_guard_blocks_unredacted_pattern_not_in_vault | DONE | |

## Task B: Privacy-Preserving Sanitization

| ID | Requirement (verbatim) | Implemented in | Proof | Status | Note |
|---|---|---|---|---|---|
| B1 | Redact sensitive regions in screenshots using blackout, masking, or other suitable techniques. | app/sanitizer.py `_blackout`, `_sensitive_boxes`; app/dom_snapshot.py `_text_range_boxes` | tests/test_guard.py::test_screenshot_is_blacked_out; docs/screens/2_switch_1440x900_light.png | DONE | Values split across sibling tags are hidden in every fragment (tests/test_adversarial.py::test_value_split_over_tags_is_hidden_in_every_fragment). The screenshot is not sent to the model. |
| B2 | Replace sensitive text with semantic placeholders such as [REDACTED:CARD] or [REDACTED:PASSWORD]. | app/sanitizer.py `sanitize`, `_Redactor` | tests/test_guard.py::test_sanitized_output_has_no_raw_values, test_same_value_same_placeholder | DONE | |
| B3 | Preserve non-sensitive information and interface structure required for AI reasoning. | app/sanitizer.py `sanitize`, `hint_for`; app/prompts.py `build_observation` | tests/test_guard.py::test_hint_has_no_digits; `tasks.task_success_pct` | DONE | Measured with the Mock planner only. |
| B4 | Ensure that original sensitive values cannot be recovered from the sanitized data sent externally. | app/sanitizer.py `sanitize`; app/guard.py `check_outbound` | tests/test_no_leak.py::test_no_annotated_value_reaches_the_ai; `tasks.leaked_values_in_ai_payloads` | DONE | Limited to the tested scenarios and the AI payload pathway. |

## Task C: AI Reasoning and Automation

| ID | Requirement (verbatim) | Implemented in | Proof | Status | Note |
|---|---|---|---|---|---|
| C1 | Integrate an LLM, VLM, or another suitable AI model to reason over sanitized information. | app/llm.py `GeminiLLM`, `MockLLM`, `get_llm` | tests/test_agent_mock.py::test_mock_completes_scenario; `gemini.task_success_pct` = 94.4 (17 of 18 runs), `gemini.leaked_values_in_ai_payloads` = 0 | DONE | Gemini (`gemini.model` = gemini-3.5-flash-lite) measured over 3 runs per scenario; success is a rate, not 100%. The model receives text only, not the screenshot. |
| C2 | Enable the AI to understand the interface and perform tasks through suitable interaction mechanisms. | app/agent.py `run`, `_step`, `_act`; app/executor.py `execute` | tests/test_agent_mock.py::test_mock_completes_scenario; `tasks.scenarios`; `gemini.successes_by_scenario` | DONE | Mock 100.0%, Gemini 94.4%. |
| C3 | Validate proposed actions and reject invalid targets or unsafe operations. | app/validator.py `parse_action`, `validate`, `_check_value` | tests/test_validator.py (7 tests); tests/test_adversarial.py::test_hidden_elements_cannot_be_used; `security.cases` | DONE | |
| C4 | Prevent the model from attempting to infer or reconstruct redacted information. | app/prompts.py system rule "Never guess, invent or reconstruct a hidden value."; app/validator.py `_check_value` | tests/test_validator.py::test_guessed_secret_rejected, test_unknown_token_and_pasted_placeholder_rejected | DONE | |
| C5 | Require user approval for sensitive or irreversible actions where appropriate. | app/validator.py `validate`; app/agent.py `_act`, `Session` | tests/test_validator.py::test_approval_flags; tests/test_acceptance.py::test_approval_sheet | DONE | Typing approval is remembered per field group; irreversible clicks ask every time. The click trigger is a label match after lookalike letters and zero-width characters are removed; unnamed submit buttons also ask (test_disguised_pay_buttons_need_approval). |

## Task D: Privacy and Security Validation

| ID | Requirement (verbatim) | Implemented in | Proof | Status | Note |
|---|---|---|---|---|---|
| D1 | Validate outgoing data before transmission and block requests containing detected, unredacted sensitive information. | app/guard.py `check_outbound`; app/agent.py `_step` | tests/test_guard.py::test_guard_blocks_raw_vault_value_and_variants, test_guard_blocks_unredacted_pattern_not_in_vault; `security.raw_page_blocked_by_guard` | DONE | |
| D2 | Implement fail-closed behavior when sanitization or validation fails. | app/agent.py `_step`, `run`; app/guard.py `check_outbound` | tests/test_guard.py::test_guard_fails_closed; `security.cases` "exception during sanitize sends nothing" | DONE | |
| D3 | Protect against prompt injection, invalid actions, and accidental data leakage through logs or metadata. | app/validator.py `validate`; app/scrub.py `scrub`; app/executor.py `block_external` | tests/test_acceptance.py::test_injection_does_not_leak_the_card; tests/test_guard.py::test_scrub_removes_values; `security.injection.card_pasted_into_feedback` | DONE | Injection tested on one page; canaries that are base64-encoded, reworded or split are not caught. |
| D4 | Provide a before/after privacy preview and an offline or local-only mode where feasible. | web/app.js switch; app/server.py `image`, `inspect`; app/llm.py `MockLLM` | tests/test_acceptance.py::test_switch_toggles_between_real_and_ai_view, test_works_offline_with_mock_ai; docs/screens/2_switch_1440x900_light.png | DONE | |
| D5 | Minimize data retention and clearly define the system's trust boundaries. | docs/threat_model.md; app/server.py `State` (in memory only); app/scrub.py `scrub` | docs/threat_model.md "Trust boundaries" | PARTIAL | Boundaries are documented; there is no test that proves retention is minimal (rules.json is persisted, session data lives in memory). |

## Evaluation scenarios

| ID | Requirement (verbatim) | Implemented in | Proof | Status | Note |
|---|---|---|---|---|---|
| S1 | E-commerce checkout: card details and addresses. | checkout scenario; app/runner.py `run_scenario` | `tasks.scenarios.checkout`; tests/test_no_leak.py::test_no_annotated_value_reaches_the_ai[checkout] | DONE | |
| S2 | Authentication: passwords, emails, and OTPs. | login scenario | `tasks.scenarios.login`; test_no_annotated_value_reaches_the_ai[login] | DONE | |
| S3 | Customer support: phone numbers and private messages. | support scenario | `tasks.scenarios.support`; test_no_annotated_value_reaches_the_ai[support] | DONE | |
| S4 | Video conferencing: faces and participant information. | video scenario; app/faces.py `find_faces`; app/dom_snapshot.py `_structure_of` | `tasks.scenarios.video`; test_no_annotated_value_reaches_the_ai[video] | PARTIAL | Names are measured (`detection.recall_by_type_pct.NAME`); face blackout has no measured number in eval/results.json. |
| S5 | Developer settings: API keys, tokens, and IP addresses. | developer scenario | `tasks.scenarios.developer`; test_no_annotated_value_reaches_the_ai[developer] | DONE | |

## Evaluation criteria

| ID | Requirement (verbatim) | Implemented in | Proof | Status | Note |
|---|---|---|---|---|---|
| E1 | PII Detection Recall: How much sensitive information is detected? | eval/run_eval.py | `detection.recall_overall_pct`, `detection.recall_by_type_pct`, `detection.items_checked` | DONE | By-type recall covers 11 types; cards and passwords are covered by the leak tests, not by a recall number. |
| E2 | Redaction Precision: How accurately is sensitive information identified without excessive redaction? | eval/run_eval.py | `detection.precision_pct`, `detection.lookalikes_checked`, `detection.lookalikes_wrongly_hidden` | DONE | |
| E3 | Privacy Leakage: Does sensitive information appear in outgoing payloads? | eval/run_eval.py; app/guard.py | `tasks.leaked_values_in_ai_payloads`, `detection.baseline`; tests/test_no_leak.py | DONE | Zero is claimed only for the tested scenarios and pathways. |
| E4 | Context Preservation: Can the AI still understand the interface after sanitization? | app/sanitizer.py; app/prompts.py | `tasks.task_success_pct`, `gemini.task_success_pct` | DONE | A real model (Gemini) completed 94.4% of runs on sanitized pages; Mock 100.0%. |
| E5 | Task Success: Can the system complete its intended task? | app/agent.py; app/runner.py | `tasks.task_success_pct`, `tasks.scenarios`, `gemini.task_success_pct` | DONE | Mock 100.0%, Gemini 94.4%. |
| E6 | Performance: What are the processing latency and resource requirements? | eval/run_eval.py | `performance.*`, `resources.*`, `machine` | DONE | |
| E7 | Security: How effectively does the system handle adversarial inputs and validation failures? | eval/adversarial_cases.json; eval/run_eval.py | `security.passed`, `security.total`, `security.injection` | DONE | |

## Deliverables

| ID | Requirement (verbatim) | Implemented in | Proof | Status | Note |
|---|---|---|---|---|---|
| V1 | Complete source code and a working demonstration. | app/, web/ | tests/test_acceptance.py (all); docs/screens/ | DONE | |
| V2 | Sensitive-information detection and sanitization pipeline. | app/detectors.py, app/sanitizer.py, app/guard.py | tests/test_detectors.py, tests/test_guard.py | DONE | |
| V3 | AI reasoning and interaction components. | app/agent.py, app/llm.py, app/validator.py, app/executor.py | tests/test_agent_mock.py, tests/test_validator.py; `gemini` | DONE | |
| V4 | Test cases, evaluation scripts, and measured results. | tests/, eval/run_eval.py | eval/results.json, eval/results.md | DONE | |
| V5 | Setup instructions and configuration files. | README.md section 2; .env.example; run.bat; run.sh; config/rules.json; config/user_profile.fake.json | README.md | DONE | A fresh-clone run has not been done (see P17). run.bat has a broken activate line; README gives manual steps. |
| V6 | A 2–3 minute demo video showing sensitive-data detection, sanitization, AI task execution, and blocking of an unsafe outgoing payload. | docs/demo_script.md | none | PARTIAL | Script and screenshots only; the video has not been recorded. |

## Documentation (README.md)

| ID | Requirement (verbatim) | Implemented in | Proof | Status | Note |
|---|---|---|---|---|---|
| R1 | Architecture diagram and data flow. | README.md section 1 | README.md | DONE | |
| R2 | Setup instructions and configuration. | README.md section 2 | README.md | DONE | |
| R3 | Detection and sanitization methodology. | README.md section 3 | README.md | DONE | |
| R4 | AI integration and action validation. | README.md section 4 | README.md | DONE | |
| R5 | Security assumptions and known limitations. | README.md section 5 | README.md | DONE | |
| R6 | Evaluation methodology and reproducible results. | README.md sections 6 and 7 | README.md | DONE | |

## Bonus points

| ID | Requirement (verbatim) | Implemented in | Proof | Status | Note |
|---|---|---|---|---|---|
| X1 | Fully local AI processing without cloud requests. | app/llm.py `MockLLM` | tests/test_acceptance.py::test_works_offline_with_mock_ai | PARTIAL | Met only by the offline scripted Mock planner; Ollama is not implemented. |
| X2 | Advanced contextual PII detection. | app/context_rules.py `find_contextual`; app/structure.py | tests/test_detectors.py::test_context_rules; `detection.recall_by_type_pct` (NAME, ADDRESS, MEDICAL) | DONE | Keyword and structure based, not a model. |
| X3 | Adaptive redaction that preserves maximum useful context. | app/sanitizer.py `hint_for`, `_Redactor` | tests/test_guard.py::test_hint_has_no_digits, test_same_value_same_placeholder | DONE | |
| X4 | Protection against prompt injection and adversarial webpages. | app/validator.py; app/executor.py `block_external`; app/prompts.py | tests/test_acceptance.py::test_injection_does_not_leak_the_card; `security.injection`; `security.cases` | DONE | |
| X5 | User-defined privacy rules and explainable redaction. | app/rules.py; app/server.py `put_rules`; app/sanitizer.py `hint_for` | tests/test_detectors.py::test_rules_can_switch_a_type_off_and_add_custom; tests/test_acceptance.py::test_user_rules_apply_on_the_next_run | DONE | |
| X6 | Local secret injection without exposing values to cloud models. | app/vault.py `Vault`; app/executor.py `fill_value` | tests/test_no_leak.py::test_profile_values_never_reach_the_ai_even_with_a_gullible_model | DONE | |
| X7 | Automated leakage testing using synthetic canary values. | app/profile.py `load_canaries_into_vault`; app/agent.py `leak_test` | tests/test_guard.py::test_guard_blocks_canary_and_short_value_as_whole_word; tests/test_acceptance.py::test_leak_test_and_stopped_message | DONE | |
| X8 | Cross-browser or desktop-agent support. | eval/run_eval.py cross-browser run | `cross_browser.chromium`, `cross_browser.webkit`, `cross_browser.firefox.skipped` | PARTIAL | Chromium and WebKit only; Firefox could not be launched on this machine. |
| X9 | Human approval for sensitive actions. | app/validator.py `validate`; app/agent.py `_act` | tests/test_acceptance.py::test_approval_sheet, test_phone_can_answer_for_the_laptop | DONE | |

## Appendix B: product promises

| ID | Requirement (verbatim) | Implemented in | Proof | Status | Note |
|---|---|---|---|---|---|
| P1 | **For everyday people, zero thinking.** The main screen shows only the task box with suggestion chips, the live view, the "See what the AI sees" switch, one status line and one narration line. Nothing else. | web/index.html, web/app.js | tests/test_acceptance.py::test_main_screen_shows_only_the_promised_parts; docs/screens/1_main_1440x900_light.png | DONE | |
| P2 | **Signature switch.** "See what the AI sees" crossfades the live view between the real page and the blacked-out version the AI receives. | web/app.js, web/style.css | test_switch_toggles_between_real_and_ai_view; docs/screens/2_switch_375x812_light.png | DONE | |
| P3 | **Human words only** on the main screen, approval sheet and status details. Technical terms appear only in "How it works". | web/app.js; app/agent.py `_narration`, `_question` | test_human_words_only; docs/screens/3_words_1440x900_light.png | DONE | |
| P4 | **Apple Pay-style approval sheet** for sensitive or irreversible actions: one plain sentence, a large Approve, a quiet Cancel, "Why am I asked?". It is a bottom sheet on phones and centered on laptops. Routine steps never interrupt. | web/app.js, web/style.css; app/agent.py `_question` | test_approval_sheet; docs/screens/4_approval_375x812_light.png, 4_approval_1440x900_light.png | DONE | |
| P5 | **Automatic light and dark** following the device setting, with no theme switch. Both themes meet 4.5:1 contrast. | web/style.css | test_automatic_light_and_dark (asserts contrast >= 4.5) | DONE | |
| P6 | **Works on phones and laptops,** from 375 px to 1440 px, with touch targets of at least 44 px. | web/style.css | test_phone_and_laptop_layout; docs/screens/6_layout_375x812_light.png | DONE | Tested at 375x812 and 1440x900 only. |
| P7 | **Phone as approval remote:** the same URL on a phone on the same Wi-Fi joins the session, and approvals appear on both devices. | app/server.py `session_state`, `approve` | test_phone_can_answer_for_the_laptop; tests/test_adversarial.py::test_phone_can_still_watch_and_approve | DONE | Tested with two browser pages on one machine, not a physical phone on Wi-Fi. |
| P8 | **Status line tells the truth:** "N things hidden · nothing private shared", or "Stopped N unsafe message(s)" when the guard blocks. | web/app.js | test_status_line_tells_the_truth; docs/screens/8_status_1440x900_light.png | DONE | |
| P9 | **Visible unsafe-payload block for the demo:** a clearly labelled "Run leak test" button in "How it works" tries to send a planted canary secret, bypassing the sanitizer for that one test request. The guard must block it, and the status line must show it. (The statement's demo video requires showing a blocked unsafe outgoing payload.) Also show the injection page being stopped. | app/agent.py `leak_test`; app/server.py `leak_test`; web/app.js | test_leak_test_and_stopped_message, test_injection_does_not_leak_the_card; docs/screens/9_leak_1440x900_light.png | DONE | |
| P10 | **Explainable redaction:** every hidden item has a human reason ("16 digits that pass the card checksum"). | app/detectors.py `Pattern` reasons; app/sanitizer.py | test_how_it_works_view; docs/screens/14_how_1440x900_light.png | DONE | |
| P11 | **User-defined privacy rules** in "How it works": per-type toggles and an "Always hide…" custom rule, which take effect on the next step. | app/rules.py; app/server.py `put_rules`; web/app.js | test_user_rules_apply_on_the_next_run | DONE | The test name says "next run"; next-step timing is not separately tested. |
| P12 | **Offline mode works with no internet** (Mock, or Ollama if installed). Gemini is used only when a key is present. | app/llm.py `MockLLM`, `get_llm`; app/server.py `set_ai` | test_works_offline_with_mock_ai; `gemini` key | PARTIAL | Mock works offline; Ollama is not implemented. |
| P13 | **Local secret injection:** the real card and password are typed by the laptop, never seen by the AI. | app/vault.py; app/executor.py `fill_value` | test_profile_values_never_reach_the_ai_even_with_a_gullible_model | DONE | |
| P14 | **"How it works" view for judges:** pipeline steps, raw vs outbound payload, validation and approval decisions, eval results, privacy settings and AI choice. | web/app.js; app/server.py `inspect`, `eval_results`, `config` | test_how_it_works_view; docs/screens/14_how_1440x900_light.png | DONE | |
| P15 | **Measured results:** a baseline of N secrets exposed without PrivacyLens vs 0 with it, plus recall, precision, task success, latency, resources, adversarial cases and cross-browser, all from `eval/results.json`. | eval/run_eval.py | `detection.baseline`, `detection.*`, `tasks.*`, `performance.*`, `resources.*`, `security.*`, `cross_browser.*` | PARTIAL | Cross-browser lacks Firefox. |
| P16 | **Natural, explainable code** that passes the section 2 style rules, with a `docs/explain/` page for every module. | docs/explain/ (18 pages, one per app module) | docs/explain/*.md | PARTIAL | Explain pages exist and were checked against the code after the security-fix pass; there is no automated style check. |
| P17 | **Fresh-clone setup works** by following only the README, on Windows and on macOS/Linux. | README.md section 2; run.bat; run.sh | none | NOT VERIFIED | README exists. Nobody has done a fresh clone and followed it on Windows, macOS or Linux. run.bat has a control character in its activate line. |

## Final-gate documents

| ID | Item | Status | Note |
|---|---|---|---|
| N1 | README.md | DONE | |
| N2 | STATUS.md | DONE | |
| N3 | docs/promise_report.md | DONE | |

## Summary

| Section | Rows | DONE | PARTIAL | NOT VERIFIED | NOT DONE |
|---|---|---|---|---|---|
| Tasks A to D | 18 | 16 | 2 | 0 | 0 |
| Evaluation scenarios | 5 | 4 | 1 | 0 | 0 |
| Evaluation criteria | 7 | 7 | 0 | 0 | 0 |
| Deliverables | 6 | 5 | 1 | 0 | 0 |
| README items | 6 | 6 | 0 | 0 | 0 |
| Bonus points | 9 | 7 | 2 | 0 | 0 |
| Appendix B promises | 17 | 13 | 3 | 1 | 0 |
| Total | 68 | 58 | 9 | 1 | 0 |

The three final-gate documents are not counted above.
