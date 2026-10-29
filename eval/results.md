# PrivacyLens evaluation

Run on Windows-11-10.0.26200-SP0, mode: quick.

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

- snapshot: median 238.3, p95 358.4
- detect: median 3.6, p95 4.9
- sanitize: median 221.5, p95 278.0
- guard: median 32.1, p95 44.3
- full_step: median 1137.5, p95 1487.4

Resources: {"peak_python_mb": 9.5, "process_rss_mb": 115.8}

Gemini: skipped: no GEMINI_API_KEY in .env

Cross-browser: "skipped in quick mode"
