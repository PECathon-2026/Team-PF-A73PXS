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

- snapshot: median 123.8, p95 179.3
- detect: median 2.3, p95 3.6
- sanitize: median 140.0, p95 193.1
- guard: median 21.8, p95 29.4
- full_step: median 819.3, p95 974.0

Resources: {"peak_python_mb": 11.6, "process_rss_mb": 123.5}

Gemini: skipped: no GEMINI_API_KEY in .env

Cross-browser: {"chromium": {"task_success_pct": 100.0, "leaks": 0}, "firefox": {"skipped": "Error"}, "webkit": {"task_success_pct": 100.0, "leaks": 0}}
