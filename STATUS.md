# Status

Last updated 2026-10-30 at the final documentation pass. Every VERIFIED item names the command or file that proves it. Anything without such proof is under NOT YET VERIFIED.

## VERIFIED

| Item | Proof |
|---|---|
| The test suite has 174 tests | `python -m pytest --collect-only -q` -> "174 tests collected" (run during this pass) |
| Full test suite passes | `python -m pytest -q` -> "174 passed, 1 warning" in the last full run, after the final code changes |
| Fresh clone works on Windows | `git clone` into a new folder, `run.bat` (venv, dependencies, server started, `/api/config` answered with Mock as default), then `python -m pytest -q` -> 174 passed and `python eval/run_eval.py --quick` -> 100% recall, 0 leaked values. |
| PII recall 100.0% of 29 annotated values | `eval/results.json`: `detection.recall_overall_pct`, `detection.items_checked` |
| Precision 100.0%, 0 of 44 lookalikes wrongly hidden | `detection.precision_pct`, `detection.lookalikes_checked`, `detection.lookalikes_wrongly_hidden` |
| Baseline: 29 values exposed without PrivacyLens, 0 with | `detection.baseline` |
| 0 annotated values or canaries in Mock AI payloads, 6 scenarios | `tasks.leaked_values_in_ai_payloads`; tests/test_no_leak.py |
| Mock task success 100.0% | `tasks.task_success_pct` |
| Gemini task success 94.4% (17 of 18 runs, gemini-3.5-flash-lite, 3 runs per scenario), 0 leaked values; the one failure was "developer: Stopped: the AI could not be reached." (service error) | `gemini.successes_by_scenario`, `gemini.failure_reasons`, `gemini.task_success_pct`, `gemini.runs_per_scenario`, `gemini.leaked_values_in_ai_payloads` |
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
| `run.bat` | Its activate line contains a control character (byte 0x07) where `\a` should be, so `call .venv\Scripts\activate.bat` likely fails. Not fixed in this pass; README gives manual steps. |
| `run.sh` on macOS and Linux | Not run. |
| Demo video | Not recorded. Script in docs/demo_script.md. |
| Firefox | `cross_browser.firefox.skipped` = "Error: BrowserType.launch: spawn UNKNOWN" on the dev machine. |
| Ollama local model | Not built. |
| Contrast beyond the acceptance test | Measured only for the elements the acceptance test checks. |
| Touch targets at widths between 375 and 1440 px | Tested at 375x812 and 1440x900 only. |
| Face blackout quality | No measured face recall in eval/results.json. |
| Browser pathway against a real exfiltration attempt in the eval | No scenario page tries an external request (`tasks.scenarios.*.blocked_requests` = 0). No test fires an external HTTP or WebSocket request at `block_external`. |
| Gemini behaviour beyond the measured runs | Only 3 runs per scenario on one model. |
| Style rules across all code | No automated style check. |
