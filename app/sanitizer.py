import io
from dataclasses import replace

from PIL import Image, ImageDraw

from app.detectors import find_sensitive
from app.faces import find_faces
from app.models import Finding, ReportItem, SanitizedSnapshot, Snapshot
from app.rules import Rules
from app.vault import Vault

CARD_BRANDS = {"4": "Visa", "5": "Mastercard", "3": "Amex", "6": "RuPay"}
KEY_PROVIDERS = {"AKIA": "AWS", "ghp_": "GitHub", "sk-": "secret key", "AIza": "Google", "xox": "Slack"}


def hint_for(finding: Finding, rules: Rules) -> str:
    """A label that says what kind of thing was hidden, never any part of the value itself."""
    if not rules.hints.get(finding.type):
        return ""
    if finding.type == "CARD":
        return CARD_BRANDS.get(finding.value.strip()[:1], "")
    if finding.type == "PHONE":
        return "phone"
    if finding.type == "IP_ADDRESS":
        return "IPv6" if ":" in finding.value else "IPv4"
    if finding.type == "API_KEY":
        return next((name for prefix, name in KEY_PROVIDERS.items() if finding.value.startswith(prefix)), "")
    return ""


class _Redactor:
    def __init__(self, vault: Vault, rules: Rules) -> None:
        self.vault = vault
        self.rules = rules
        self.report: dict[str, ReportItem] = {}

    def note(self, type_: str, value: str, reason: str, source: str, hint: str = "") -> str:
        placeholder = self.vault.add(type_, value, hint)
        self.report.setdefault(placeholder, ReportItem(type_, placeholder, reason, source))
        return placeholder

    def text(self, text: str) -> str:
        for f in reversed(find_sensitive(text, self.rules)):
            placeholder = self.note(f.type, f.value, f.reason, f.source, hint_for(f, self.rules))
            text = text[:f.start] + placeholder + text[f.end:]
        return text


def _blackout(png: bytes, boxes: list[tuple[float, float, float, float]]) -> bytes:
    image = Image.open(io.BytesIO(png)).convert("RGB")
    draw = ImageDraw.Draw(image)
    for x, y, w, h in boxes:
        draw.rectangle([x - 2, y - 2, x + w + 2, y + h + 2], fill="black")
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def _sensitive_boxes(snap: Snapshot, rules: Rules) -> list[tuple[float, float, float, float]]:
    boxes = [box for _, box in snap.text_boxes]
    for e in snap.elements:
        if (e.sensitive_type and e.value) or e.tag == "video":
            boxes.append(e.box)
    if rules.on("FACE"):
        boxes += [tuple(float(v) for v in b) for b in find_faces(snap.screenshot)]
    return boxes


def sanitize(snap: Snapshot, vault: Vault, rules: Rules) -> SanitizedSnapshot:
    red = _Redactor(vault, rules)
    elements = []
    for e in snap.elements:
        value = e.value
        if e.sensitive_type and e.value and rules.on(e.sensitive_type):
            value = red.note(e.sensitive_type, e.value, e.sensitive_reason, "structure")
        else:
            value = red.text(e.value)
        elements.append(replace(e, text=red.text(e.text), label=red.text(e.label), value=value, selector=""))
    return SanitizedSnapshot(
        url=red.text(snap.url),
        elements=elements,
        page_text=red.text(snap.page_text),
        aria=red.text(snap.aria),
        screenshot=_blackout(snap.screenshot, _sensitive_boxes(snap, rules)),
        report=list(red.report.values()),
        element_types={e.id: e.sensitive_type for e in snap.elements if e.sensitive_type},
    )
