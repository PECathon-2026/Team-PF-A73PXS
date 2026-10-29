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
    action: str        # click | type | select | scroll | wait | done | ask_user | reveal
    target: str        # element id, "" when not needed
    value: str         # may contain {{TYPE#n}} tokens; for reveal, exactly one token
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
| detectors | `find_sensitive(text: str, rules: Rules) -> list[Finding]` | normalizes first, then runs pattern, context and custom rules; each runs only if `rules.on(type)`, i.e. the type is not revealed; saved-vault matches of revealed types are skipped; custom rules and canaries always run |
| detectors | `luhn_valid(digits: str) -> bool`, `verhoeff_valid(digits: str) -> bool` | |
| context_rules | `find_contextual(text: str) -> list[Finding]` | NAME, ADDRESS, DOB, MEDICAL |
| faces | `find_faces(png: bytes) -> list[tuple[int, int, int, int]]` | OpenCV Haar cascade |
| dom_snapshot | `take_snapshot(page) -> Snapshot` | async |
| vault | `Vault.add(finding) -> str` returns the placeholder; `Vault.resolve(token) -> str`; `Vault.values()`; `Vault.clear()` | memory only |
| sanitizer | `sanitize(snap: Snapshot, vault: Vault, rules: Rules) -> SanitizedSnapshot` | |
| prompts | `build_observation(task, snap, vault, history, rules) -> str` | JSON with task, url, secrets, ask_kinds (sorted kinds in Ask mode, not yet shared, with a token in secrets), elements, page_text, outline (sanitized ARIA without `- /attr:` property lines or form-field values, first 2000 characters), history |
| guard | `check_outbound(payload: str, vault: Vault, rules: Rules) -> GuardResult` | fail closed; skips vault values and detector findings of revealed types only; canaries and custom rules always block |
| scrub | `scrub(text: str, vault: Vault) -> str` | removes vault values from any message |
| llm | `next_action(self, system: str, observation: str) -> str` on `GeminiLLM`, `MockLLM`, `RecordingLLM` | Gemini, Mock, Recording wrapper |
| validator | `validate(action: Action, snap: SanitizedSnapshot, vault: Vault, rules: Rules) -> ValidationResult` | reveal: known token whose type is in Ask mode, needs_approval; already revealed: ok, no approval; redact: rejected. Typed literals of revealed types are allowed |
| executor | `execute(page, action, snap, vault, profile) -> None` | injects vault values locally |
| agent | `run_task(session) -> AsyncIterator[AuditEvent]` | step budget 12 |

## Rules

- A placeholder is `[REDACTED:TYPE#n]`. The model refers to a secret as `{{TYPE#n}}`.
- The same value always maps to the same placeholder within a session.
- Only `sanitizer` output and the model's own replies may cross the outbound boundary; `guard.check_outbound` runs on every outbound string.
- Any exception in snapshot, sanitize or guard blocks the step. Nothing is sent.

## Privacy choices

```python
@dataclass
class Rules:
    modes: dict[str, str]   # TYPE -> redact | ask | reveal; every type defaults to ask, unknown types read as ask
    hints: dict[str, bool]
    custom: list[str]       # Always hide patterns

    def mode(self, type_: str) -> str        # CUSTOM always reads redact
    def on(self, type_: str) -> bool         # mode != reveal: the type is hidden from the AI
    def with_shared(self, types) -> Rules    # copy with those types set to reveal
```

- `redact`: hidden, and the AI cannot ask for it. `ask`: hidden; the AI may send `{"action": "reveal", "value": "{{TYPE#n}}", "reason": "..."}` and the user is asked "Let the AI read your <kind> for this task?". `reveal`: the AI sees the real value. Every type may be set to reveal except CUSTOM.
- `config/rules.json` is `{"modes": {...}, "hints": {...}, "custom": [...]}`. `load_rules` ignores an old `enabled` key and drops unknown types or modes.
- `Session.shared_types` holds kinds approved during one task. It is never saved and starts empty for every session. Each step uses `session.rules.with_shared(session.shared_types)` for snapshot, sanitize, observation, validation and guard, so saved changes apply from the next step.
- A revealed type is not detected, not replaced in text, and gets no screenshot box. Frames, canvases and video are always covered.

## HTTP

- `GET /api/rules` returns `{"modes": {TYPE: mode for every type}, "hints": {...}, "custom": [...]}`. `PUT /api/rules` takes any subset of those keys, merges `modes`, saves, and returns the same shape; a bad type or mode, or CUSTOM set to anything but redact, is a 400.
- `GET /api/session` includes `"shared": [{"type": ..., "by": "choice" | "approval"}]`, and `approval` is `{"question", "why", "kind": "share" | "action"}`.
