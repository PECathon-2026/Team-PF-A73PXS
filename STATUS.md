# Status

Last updated 2026-10-30, after adding Privacy choices, the hidden-item banner and the Windows build. Every VERIFIED item names the command or file that proves it. Anything without such proof is under NOT YET VERIFIED.

## VERIFIED

| Item | Proof |
|---|---|
| The test suite has 212 tests | `python -m pytest --collect-only -q` -> "212 tests collected" (run during this pass) |
| Full test suite passes | `python -m pytest -q` -> "212 passed" in the last full run, after the final code changes |
| Every kind defaults to Ask permission; CUSTOM stays Hide; an old `enabled` key and bad modes are ignored | tests/test_choices.py::test_every_type_defaults_to_ask_and_custom_stays_redact, test_load_rules_ignores_enabled_and_bad_modes; config/rules.json |
| Hide and Ask keep the value out of text, screenshot and payload; Reveal lets only that kind through sanitizer and guard | tests/test_choices.py::test_hidden_modes_keep_the_value_out, test_reveal_lets_the_value_through_sanitize_and_guard |
| Canaries and Always hide rules stay blocked even with every kind on Reveal | tests/test_choices.py::test_canary_and_custom_rules_stay_blocked_when_everything_is_revealed; tests/test_detectors.py::test_custom_rules_stay_hidden_even_if_custom_is_marked_reveal |
| `reveal` is refused for Hide, needs approval for Ask, needs none once shared; unknown tokens refused | tests/test_choices.py::test_reveal_action_needs_ask_mode |
| A revealed value may be typed as literal text; a hidden one may not | tests/test_choices.py::test_revealed_literal_may_be_typed_but_hidden_one_may_not |
| `ask_kinds` lists only unshared Ask kinds with a token | tests/test_choices.py::test_ask_kinds_lists_only_unshared_kinds_with_a_token |
| Approvals do not carry over to the next task | tests/test_choices.py::test_shared_types_do_not_carry_over_to_the_next_task |
| Mock demo task "Ask support to verify my Aadhaar number": the share question and buttons appear, an approved share reaches the AI from the next step only, the PAN never does, the task succeeds; a refused share stops the run with nothing shared | tests/test_choices.py::test_approved_share_reaches_the_ai_from_the_next_step, test_cancelled_share_stops_the_run; docs/screens/privacy_ask_share_1440x900_light.png, privacy_ask_after_1440x900_light.png |
| `PUT /api/rules` merges modes and refuses bad ones | tests/test_choices.py::test_put_rules_merges_modes_and_rejects_bad_ones; tests/test_server.py::test_put_rules_rejects_bad_types |
| A Reveal choice saved through the API applies to the next run | tests/test_acceptance.py::test_user_rules_apply_on_the_next_run |
| How it works shows the "Hide: N · Ask permission: N · Reveal: N" summary and an "Open Privacy choices" button | tests/test_acceptance.py::test_how_it_works_view; docs/screens/14_how_1440x900_light.png |
| Privacy choices panel and the Reveal confirmation exist and render at 1440 and 375 px | docs/screens/privacy_choices_1440x900_light.png, privacy_choices_375x812_dark.png, privacy_choices_confirm_1440x900_light.png (screenshots; no test writes these files) |
| Hidden-item banner names new items in the agreed forms and has `role="status"`; it stays quiet on a page opened after items were hidden | tests/test_acceptance.py::test_hidden_banner_names_new_items, test_hidden_banner_stays_quiet_for_items_hidden_before_load; docs/screens/hidden_banner_1440x900_light.png, hidden_banner_375x812_dark.png |
| After the Privacy choices change, a quick Mock run with the default all-Ask settings reproduced the Mock numbers: recall 100% of 29, precision 100% (0 of 44 lookalikes hidden), 0 leaked values, 100% task success, 20 of 20 adversarial | `python eval/run_eval.py --quick`. Its output was not kept as the official file; `eval/results.json` still holds the earlier full run because that run has the Gemini row. |
| Windows build: `packaging\build_exe.bat` produces `dist\PrivacyLens\PrivacyLens.exe` and `dist\PrivacyLens-windows.zip` (241,240,364 bytes); the folder is about 570 MB; the zip contains `.env.example` and no `.env` | build run on the dev PC; zip listing |
| The exe runs without Python: built from the final code and started from another working folder with only `C:\Windows\System32` on PATH; `/api/config` answered (Mock); the page included Privacy choices; the default modes were all Ask; a support task with the verify wording asked for a share, was approved and finished successfully with nothing blocked | manual clean-environment run on the dev PC |
| Fresh clone works on Windows (before the Privacy choices change) | `git clone` into a new folder, `run.bat` (venv, dependencies, server started, `/api/config` answered with Mock as default), then `python -m pytest -q` -> 174 passed (test count at that time) and `python eval/run_eval.py --quick` -> 100% recall, 0 leaked values. |
| PII recall 100.0% of 29 annotated values | `eval/results.json`: `detection.recall_overall_pct`, `detection.items_checked` |
| Precision 100.0%, 0 of 44 lookalikes wrongly hidden | `detection.precision_pct`, `detection.lookalikes_checked`, `detection.lookalikes_wrongly_hidden` |
| Baseline: 29 values exposed without PrivacyLens, 0 with | `detection.baseline` |
| 0 annotated values or canaries in Mock AI payloads, 6 scenarios, every kind hidden (nothing revealed or approved) | `tasks.leaked_values_in_ai_payloads`; tests/test_no_leak.py |
| Mock task success 100.0% | `tasks.task_success_pct` |
| Gemini task success 94.4% (17 of 18 runs, gemini-3.5-flash-lite, 3 runs per scenario), 0 leaked values; the one failure was "developer: Stopped: the AI could not be reached." (service error) | `gemini.successes_by_scenario`, `gemini.failure_reasons`, `gemini.task_success_pct`, `gemini.runs_per_scenario`, `gemini.leaked_values_in_ai_payloads`. Official, measured before the fallback chain. |
| Separate benchmark, not in `eval/results.json`: Gemini 20/24 (83.3%) before the fallback chain, 24/24 (100%) with it; a later re-measure of the final default fallbacks was invalid (daily quota used up, all models 429) | `eval/gemini_benchmark.txt`, `eval/gemini_bench.py` |
| 20 of 20 adversarial cases pass | `security.passed`, `security.total` |
| A raw unsanitized page is blocked by the guard | `security.raw_page_blocked_by_guard` |
| The injection page does not get the card pasted; 3 attempts rejected | `security.injection.card_pasted_into_feedback`, `security.injection.attempts_rejected_by_validator`; tests/test_agent_mock.py::test_fooled_ai_is_stopped_on_the_injection_page |
| eval/results.json is from the final full eval run (mode: full) | `eval/results.json` `mode` |
| Latency and memory measured | `performance.*`, `resources.*` |
| Chromium and WebKit: 100.0% success, 0 leaks | `cross_browser.chromium`, `cross_browser.webkit` |
| Leak test button blocks a planted canary and the status line shows it | tests/test_acceptance.py::test_leak_test_and_stopped_message; docs/screens/9_leak_1440x900_light.png |
| Main screen, switch, human words, approval sheet, layout at 375 and 1440 px, status line, How it works | tests/test_acceptance.py; docs/screens/ |
| Both themes meet 4.5:1 contrast for the checked elements | tests/test_acceptance.py::test_automatic_light_and_dark |
| A second page (phone size) can answer an approval for the laptop | tests/test_acceptance.py::test_phone_can_answer_for_the_laptop |
| Raw views, settings and runs refuse requests from other machines; unknown Host headers are refused | tests/test_adversarial.py::test_raw_views_are_local_only, test_unknown_host_header_is_refused |
| WebRTC constructors are removed from session pages | tests/test_adversarial.py::test_webrtc_is_removed_from_session_pages |
| Slow custom rules are refused on save | tests/test_adversarial.py::test_slow_custom_rule_is_refused |
| Premature "done" is rejected | tests/test_agent_mock.py::test_done_before_any_step_is_rejected_and_the_task_still_finishes |

## NOT YET VERIFIED

| Item | Why |
|---|---|
| Real phone on the same Wi-Fi as approval remote | Only simulated with a second browser page on one machine. Firewall prompt and Host-header address matching not tried on a real LAN. |
| Fresh clone set up by following only the README (P17) | macOS and Linux (`run.sh`) not run. On Windows the fresh clone was done and is under VERIFIED. |
| `run.sh` on macOS and Linux | Not run. `run.bat` on Windows was run successfully in the fresh-clone test (see VERIFIED). |
| `run.sh` on macOS and Linux | Not run. |
| Demo video | Not recorded. Script in docs/demo_script.md. |
| Firefox | `cross_browser.firefox.skipped` = "Error: BrowserType.launch: spawn UNKNOWN" on the dev machine. |
| Ollama local model | Not built. |
| Contrast beyond the acceptance test | Measured only for the elements the acceptance test checks. |
| Touch targets at widths between 375 and 1440 px | Tested at 375x812 and 1440x900 only. |
| Face blackout quality | No measured face recall in eval/results.json. |
| Browser pathway against a real exfiltration attempt in the eval | No scenario page tries an external request (`tasks.scenarios.*.blocked_requests` = 0). No test fires an external HTTP or WebSocket request at `block_external`. |
| Gemini behaviour beyond the measured runs | Only 3 runs per scenario on one model. |
| Official Gemini number after the fallback chain | 94.4% predates the chain. Re-run `python eval/run_eval.py` after the free-tier daily quota resets. |
| Final default fallbacks in a real run | `gemini-3.6-flash,gemini-3.5-flash` is covered by unit tests only; the re-measure hit the daily quota. `gemini-3.8-flash` timed out in testing and is not a default. |
| Per-call model in eval results | `eval/results.json` records only `GEMINI_MODEL`; the audit log shows the model per call. |
| Free-tier quota | The daily quota is the ceiling; each run uses roughly 3 to 13 calls. |
| Style rules across all code | No automated style check. |
| Gemini with the `reveal` action and the new system prompt | Not run. The free daily quota was used up. Whether Gemini asks for a share at the right moment, or at all, is unknown. |
| Official eval with Privacy choices | `eval/results.json` predates the change. Only a quick Mock run was repeated (see VERIFIED). |
| Leak numbers with a kind revealed or approved | Not measured, by design: a shared kind reaches the AI. The 0-leak claims apply to the default settings only. |
| A Privacy choice saved in the middle of a run applying at the next step | Code reads the rules object at the start of every step; the acceptance test checks the next run, not the next step. |
| Hint labels | The UI no longer has hint switches; hints work only through rules.json or `PUT /api/rules`. Not re-tested in the UI. |
| Privacy choices panel clicks (radio control saving, Reveal confirmation, Always hide add and remove, link hidden on a phone) | No automated UI test clicks through the panel. The server side is tested (`put_rules`); the panel itself is covered by screenshots only. |
| Banner pause on hover and focus, queueing while sheets are open, reduced-motion fade | In the code (web/app.js, web/style.css); no test covers them. |
| Windows exe on another PC | Built and run on the dev PC only. |
| Browser opening by itself when the exe starts | The clean-environment check ran headless. |
| Windows SmartScreen | The exe is not signed; a warning is likely ("More info", then "Run anyway"). Not observed on a fresh PC. |
| Gemini through the exe | Not tried. |
| Quick eval and custom-rule speed check from inside the exe | Both start `sys.executable`, which the launcher handles; not run from the exe. |
| macOS and Linux builds | Not built. `build_exe.bat` is Windows only. |
