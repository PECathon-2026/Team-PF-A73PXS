# Contracts

Shared data shapes and function signatures. All modules in `app/` follow these. Dataclasses live in `app/models.py`.

## Data shapes

```python
@dataclass(frozen=True)
class Finding:
    type: str          # CARD, AADHAAR, PAN, EMAIL, PHONE, OTP, PASSWORD, API_KEY,
                       # IP_ADDRESS, UPI, IFSC, CVV, NAME, ADDRESS, DOB, MEDICAL, FACE, CUSTOM
    start: int         # offset into the text that was scanned (-1 for structural findings)
    end: int
    value: str         # raw value; lives only in memory, never logged or sent
    reason: str        # human reason, e.g. "16 digits that pass the card checksum"
    source: str        # pattern | structure | context | vision

@dataclass
class Element:
    id: str            # e1, e2 ... stable within one snapshot
    tag: str
    role: str
    label: str         # label, placeholder or aria-label
    text: str          # visible text
    value: str         # current value of an input
    input_type: str    # type or autocomplete hint
    box: tuple[float, float, float, float]   # x, y, w, h
    selector: str      # CSS selector captured at snapshot time (local only)
    can_click: bool
    can_type: bool
    hidden: bool

@dataclass
class Snapshot:
    url: str
    elements: list[Element]
    page_text: str     # full text including hidden text
    aria: str
    screenshot: bytes  # PNG, local only

@dataclass
class SanitizedSnapshot:
    url: str
    elements: list[Element]    # same ids, sensitive strings replaced by placeholders
    page_text: str
    aria: str                  # sanitized accessibility tree; sent as "outline" (see prompts below)
    screenshot: bytes          # solid blackout over every sensitive region
    report: list[ReportItem]   # type, placeholder, reason, source; never the raw value

@dataclass
class Action:
    action: str        # click | type | select | scroll | wait | done | ask_user
    target: str        # element id, "" when not needed
    value: str         # may contain {{TYPE#n}} tokens
    reason: str

@dataclass
class ValidationResult:
    ok: bool
    needs_approval: bool
    reason: str        # human-readable

@dataclass
class GuardResult:
    allowed: bool
    reason: str        # placeholders only, never raw values

@dataclass
class AuditEvent:
    step: int
    kind: str          # snapshot | sanitize | guard | llm | validate | approval | execute | block
    detail: str        # scrubbed
```

## Functions

| Module | Signature | Notes |
|---|---|---|
| detectors | `find_sensitive(text: str, rules: Rules) -> list[Finding]` | normalizes first, then runs pattern, context and custom rules; each runs only if `rules.on(type)` (custom rules under CUSTOM); the guard always scans every type |
| detectors | `luhn_valid(digits: str) -> bool`, `verhoeff_valid(digits: str) -> bool` | |
| context_rules | `find_contextual(text: str) -> list[Finding]` | NAME, ADDRESS, DOB, MEDICAL |
| faces | `find_faces(png: bytes) -> list[tuple[int, int, int, int]]` | OpenCV Haar cascade |
| dom_snapshot | `take_snapshot(page) -> Snapshot` | async |
| vault | `Vault.add(finding) -> str` returns the placeholder; `Vault.resolve(token) -> str`; `Vault.values()`; `Vault.clear()` | memory only |
| sanitizer | `sanitize(snap: Snapshot, vault: Vault, rules: Rules) -> SanitizedSnapshot` | |
| prompts | `build_observation(task, snap, vault, history) -> str` | JSON with task, url, secrets, elements, page_text, outline (sanitized ARIA without `- /attr:` property lines or form-field values, first 2000 characters), history |
| guard | `check_outbound(payload: str, vault: Vault, rules: Rules) -> GuardResult` | fail closed |
| scrub | `scrub(text: str, vault: Vault) -> str` | removes vault values from any message |
| llm | `next_action(self, system: str, observation: str) -> str` on `GeminiLLM`, `MockLLM`, `RecordingLLM` | Gemini, Mock, Recording wrapper |
| validator | `validate(action: Action, snap: SanitizedSnapshot, vault: Vault) -> ValidationResult` | |
| executor | `execute(page, action, snap, vault, profile) -> None` | injects vault values locally |
| agent | `run_task(session) -> AsyncIterator[AuditEvent]` | step budget 12 |

## Rules

- A placeholder is `[REDACTED:TYPE#n]`. The model refers to a secret as `{{TYPE#n}}`.
- The same value always maps to the same placeholder within a session.
- Only `sanitizer` output and the model's own replies may cross the outbound boundary; `guard.check_outbound` runs on every outbound string.
- Any exception in snapshot, sanitize or guard blocks the step. Nothing is sent.
