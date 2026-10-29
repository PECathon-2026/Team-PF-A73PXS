# Promise report

One row per bullet group of PS-004 (Appendix A of docs/ps004_and_promises.md) and one row per agreed product promise (Appendix B). Numbers come from eval/results.json, cited by key. Row-by-row detail is in docs/requirements_matrix.md.

Status: PASS, PARTIAL, FAIL, NOT DONE. NOT VERIFIED is used where the work exists but nobody has run the check.

## Appendix A: PS-004

| Group | Evidence | Status | Note |
|---|---|---|---|
| A) Sensitive Information Detection | tests/test_detectors.py::test_each_type, test_context_rules, test_lookalikes_are_not_flagged; `detection.recall_overall_pct` 100.0, `detection.precision_pct` 100.0 | PARTIAL | Patterns, structure and defence in depth done. AI-based detection is a Haar face detector plus keyword rules; no NER, no OCR, face blackout not measured. |
| B) Privacy-Preserving Sanitization | tests/test_guard.py::test_screenshot_is_blacked_out, test_sanitized_output_has_no_raw_values; tests/test_adversarial.py::test_value_split_over_tags_is_hidden_in_every_fragment; `detection.baseline.secrets_exposed_with` 0 | PASS | |
| C) AI Reasoning and Automation | tests/test_agent_mock.py::test_mock_completes_scenario; tests/test_validator.py; `tasks.task_success_pct` 100.0; `gemini.task_success_pct` 88.9 | PASS | Gemini success is a measured rate, not 100%. |
| D) Privacy and Security Validation | tests/test_guard.py::test_guard_fails_closed; tests/test_acceptance.py::test_switch_toggles_between_real_and_ai_view, test_works_offline_with_mock_ai; `security.raw_page_blocked_by_guard` true | PARTIAL | Retention is memory only by design and documented, but no test proves it. |
| Technical requirements (measurable protection) | eval/run_eval.py; eval/results.json | PASS | |
| Evaluation scenarios 1 to 5 | `tasks.scenarios` (checkout, login, support, video, developer, plus injection); tests/test_no_leak.py::test_no_annotated_value_reaches_the_ai | PARTIAL | Video scenario: participant names measured, faces not measured. |
| Evaluation criteria (recall, precision, leakage, context, task success, performance, security) | `detection.*`, `tasks.*`, `gemini.*`, `performance.*`, `resources.*`, `security.*` | PASS | Zero leakage claimed only for 6 scenarios and 2 pathways. |
| Deliverables | app/, web/, tests/, eval/, README.md, .env.example, config/ | PARTIAL | Demo video not recorded. |
| Documentation (README.md items 1 to 6) | README.md sections 1 to 6 | PASS | |
| Bonus points | see below | PARTIAL | 7 of 9 met. |

### Bonus points

| Bonus | Evidence | Status | Note |
|---|---|---|---|
| Fully local AI processing without cloud requests | tests/test_acceptance.py::test_works_offline_with_mock_ai | PARTIAL | Only the scripted Mock runs offline. Ollama not built. |
| Advanced contextual PII detection | tests/test_detectors.py::test_context_rules; `detection.recall_by_type_pct` NAME, ADDRESS, MEDICAL, ACCOUNT 100.0 | PASS | Keyword and structure rules, not a model. |
| Adaptive redaction that preserves maximum useful context | tests/test_guard.py::test_hint_has_no_digits, test_same_value_same_placeholder | PASS | |
| Protection against prompt injection and adversarial webpages | tests/test_agent_mock.py::test_fooled_ai_is_stopped_on_the_injection_page; `security.injection`; `security.passed` 20 of `security.total` 20 | PASS | One injection page. |
| User-defined privacy rules and explainable redaction | tests/test_acceptance.py::test_user_rules_apply_on_the_next_run, test_how_it_works_view | PASS | |
| Local secret injection | tests/test_no_leak.py::test_profile_values_never_reach_the_ai_even_with_a_gullible_model | PASS | |
| Automated leakage testing with canaries | tests/test_guard.py::test_guard_blocks_canary_and_short_value_as_whole_word; tests/test_acceptance.py::test_leak_test_and_stopped_message | PASS | |
| Cross-browser or desktop-agent support | `cross_browser.chromium`, `cross_browser.webkit` 100.0% and 0 leaks each | PARTIAL | Firefox skipped (spawn UNKNOWN). |
| Human approval for sensitive actions | tests/test_acceptance.py::test_approval_sheet; tests/test_adversarial.py::test_disguised_pay_buttons_need_approval | PASS | |

## Appendix B: product promises

| # | Promise | Evidence | Status | Note |
|---|---|---|---|---|
| 1 | Everyday people, zero thinking | tests/test_acceptance.py::test_main_screen_shows_only_the_promised_parts; docs/screens/1_main_1440x900_light.png | PASS | |
| 2 | Signature switch | test_switch_toggles_between_real_and_ai_view; docs/screens/2_switch_1440x900_light.png | PASS | |
| 3 | Human words only | test_human_words_only; docs/screens/3_words_1440x900_light.png | PASS | |
| 4 | Apple Pay-style approval sheet | test_approval_sheet; docs/screens/4_approval_375x812_light.png, 4_approval_1440x900_light.png | PASS | |
| 5 | Automatic light and dark, 4.5:1 contrast | test_automatic_light_and_dark; docs/screens/1_main_1440x900_dark.png | PASS | Contrast measured only for the elements the test checks. |
| 6 | Phones and laptops, 375 to 1440 px, 44 px targets | test_phone_and_laptop_layout; docs/screens/6_layout_375x812_light.png | PASS | Checked at 375x812 and 1440x900 only. |
| 7 | Phone as approval remote | test_phone_can_answer_for_the_laptop; tests/test_adversarial.py::test_phone_can_still_watch_and_approve | PARTIAL | Simulated with a second browser page; not tried with a real phone on Wi-Fi. |
| 8 | Status line tells the truth | test_status_line_tells_the_truth; docs/screens/8_status_1440x900_light.png | PASS | |
| 9 | Visible unsafe-payload block and injection page stopped | test_leak_test_and_stopped_message, test_injection_does_not_leak_the_card; docs/screens/9_leak_1440x900_light.png | PASS | Leak test checks the guard alone, by design. |
| 10 | Explainable redaction | test_how_it_works_view; docs/screens/14_how_1440x900_light.png | PASS | |
| 11 | User-defined privacy rules | test_user_rules_apply_on_the_next_run | PASS | Tested on the next run; next-step timing not tested separately. |
| 12 | Offline mode | test_works_offline_with_mock_ai | PARTIAL | Mock only; Ollama not implemented. |
| 13 | Local secret injection | test_profile_values_never_reach_the_ai_even_with_a_gullible_model; test_each_secret_goes_into_its_own_field | PASS | |
| 14 | "How it works" view | test_how_it_works_view; docs/screens/14_how_1440x900_light.png | PASS | |
| 15 | Measured results | `detection.baseline` 29 vs 0, `detection.*`, `tasks.*`, `performance.*`, `resources.*`, `security.*`, `cross_browser.*` | PARTIAL | Firefox missing from cross-browser. |
| 16 | Natural, explainable code with docs/explain pages | docs/explain/ (18 pages) | PARTIAL | Pages checked against code in the final pass; no automated style check. |
| 17 | Fresh-clone setup works from the README | README.md section 2 | NOT VERIFIED | Not run on any OS. run.bat has a broken activate line. |
