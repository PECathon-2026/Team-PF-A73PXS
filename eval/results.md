# PrivacyLens evaluation

Run on Windows-11-10.0.26200-SP0, mode: full.

| Measure | Result |
|---|---|
| PII recall | 100.0% of 29 annotated values |
| Redaction precision | 100.0% (0 of 44 lookalikes wrongly hidden) |
| Exposed without PrivacyLens | 29 values |
| Exposed with PrivacyLens | 0 values |
| Leaked into AI payloads | 0 across 6 scenarios |
| Task success (Mock) | 100.0% |
| Adversarial cases | 20 of 20 pass |

Recall by type:

- AADHAAR: 100.0%
- ACCOUNT: 100.0%
- ADDRESS: 100.0%
- API_KEY: 100.0%
- EMAIL: 100.0%
- IP_ADDRESS: 100.0%
- MEDICAL: 100.0%
- NAME: 100.0%
- OTP: 100.0%
- PAN: 100.0%
- PHONE: 100.0%

Latency (ms):

- snapshot: median 149.5, p95 229.6
- detect: median 4.0, p95 10.0
- sanitize: median 152.4, p95 239.1
- guard: median 66.6, p95 137.8
- full_step: median 1419.1, p95 1723.7

Resources: {"peak_python_mb": 13.8, "process_rss_mb": 130.4}

Gemini: {"model": "gemini-3.5-flash-lite", "runs_per_scenario": 3, "task_success_pct": 88.9, "successes_by_scenario": {"checkout": 2, "login": 2, "support": 3, "video": 3, "developer": 3, "injection": 3}, "failure_reasons": ["checkout: Stopped: the AI could not be reached.", "login: Stopped: the AI needs your help."], "leaked_values_in_ai_payloads": 0}

Cross-browser: {"chromium": {"task_success_pct": 100.0, "leaks": 0}, "firefox": {"skipped": "Error: BrowserType.launch: spawn UNKNOWN"}, "webkit": {"task_success_pct": 100.0, "leaks": 0}}
