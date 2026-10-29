from dataclasses import dataclass, field


@dataclass(frozen=True)
class Finding:
    type: str
    start: int
    end: int
    value: str
    reason: str
    source: str
    confidence: float = 0.9


@dataclass
class Element:
    id: str
    tag: str
    role: str = ""
    label: str = ""
    text: str = ""
    value: str = ""
    input_type: str = ""
    box: tuple[float, float, float, float] = (0, 0, 0, 0)
    selector: str = ""
    sensitive_type: str = ""
    sensitive_reason: str = ""
    can_click: bool = False
    can_type: bool = False
    hidden: bool = False


@dataclass
class Snapshot:
    url: str
    elements: list[Element]
    page_text: str
    aria: str
    screenshot: bytes
    text_boxes: list[tuple[str, tuple[float, float, float, float]]] = field(default_factory=list)


@dataclass
class ReportItem:
    type: str
    placeholder: str
    reason: str
    source: str


@dataclass
class SanitizedSnapshot:
    url: str
    elements: list[Element]
    page_text: str
    aria: str
    screenshot: bytes
    report: list[ReportItem]
    element_types: dict[str, str] = field(default_factory=dict)


@dataclass
class Action:
    action: str
    target: str = ""
    value: str = ""
    reason: str = ""


@dataclass
class ValidationResult:
    ok: bool
    needs_approval: bool = False
    reason: str = ""


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""


@dataclass
class AuditEvent:
    step: int
    kind: str
    detail: str
