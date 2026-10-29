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

- snapshot: median 144.9, p95 187.0
- detect: median 4.3, p95 7.2
- sanitize: median 159.3, p95 242.2
- guard: median 99.4, p95 165.1
- full_step: median 1035.9, p95 1172.6

Resources: {"peak_python_mb": 13.5, "process_rss_mb": 133.9}

Gemini: {"model": "gemini-3.5-flash-lite", "runs_per_scenario": 3, "task_success_pct": 94.4, "successes_by_scenario": {"checkout": 3, "login": 3, "support": 3, "video": 3, "developer": 2, "injection": 3}, "failure_reasons": ["developer: Stopped: the AI could not be reached."], "leaked_values_in_ai_payloads": 0}

Cross-browser: {"chromium": {"task_success_pct": 100.0, "leaks": 0}, "firefox": {"skipped": "Error: BrowserType.launch: spawn UNKNOWN"}, "webkit": {"task_success_pct": 100.0, "leaks": 0}}
