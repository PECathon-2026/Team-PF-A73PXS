import io
import re
from dataclasses import replace
from urllib.parse import unquote_plus

from PIL import Image, ImageDraw

from app.detectors import find_sensitive
from app.faces import find_faces
from app.models import Element, Finding, ReportItem, SanitizedSnapshot, Snapshot
from app.rules import Rules
from app.vault import Vault

WHOLE_BOX_TAGS = {"video", "iframe", "canvas"}
PERSON_IMAGE = re.compile(r"avatar|participant|profile|face|photo|portrait|camera", re.I)
CARD_BRANDS = {"4": "Visa", "5": "Mastercard", "3": "Amex", "6": "RuPay"}
KEY_PROVIDERS = {"AKIA": "AWS", "ghp_": "GitHub", "sk-": "secret key", "AIza": "Google", "xox": "Slack"}


def hint_for(finding: Finding, rules: Rules) -> str:
    """A label for the kind of thing that was hidden (for a card, its network name), never digits or fragments."""
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
        for f in reversed(find_sensitive(text, self.rules, self.vault)):
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


def _sensitive_boxes(snap: Snapshot, rules: Rules, changed: set[str]) -> list[tuple[float, float, float, float]]:
    """Text found sensitive, plus whole elements whose content cannot be checked (frames, canvases, video)."""
    boxes = [box for _, box in snap.text_boxes]
    for e in snap.elements:
        structural = e.sensitive_type and (e.value or (e.text and not e.can_type))
        person = e.tag == "img" and PERSON_IMAGE.search(e.label)
        if structural or person or e.id in changed or e.tag in WHOLE_BOX_TAGS:
            boxes.append(e.box)
    if rules.on("FACE"):
        boxes += [tuple(float(v) for v in b) for b in find_faces(snap.screenshot)]
    return boxes


def _structural_placeholder(e: Element, red: _Redactor, rules: Rules) -> dict[str, str]:
    """Hide values that are sensitive because of where they sit (a password box, a name tile)."""
    if not (e.sensitive_type and rules.on(e.sensitive_type)):
        return {}
    if e.value:
        return {"value": red.note(e.sensitive_type, e.value, e.sensitive_reason, "structure")}
    if e.text and not e.can_type:
        return {"text": red.note(e.sensitive_type, e.text, e.sensitive_reason, "structure")}
    return {}


def _split_placeholders(snap: Snapshot, red: _Redactor) -> dict[str, str]:
    """A value split over sibling tags (<b>4111</b><b>1111</b>...) is only visible in the parent's text,
    so find it there and hide every fragment that is part of it."""
    hidden: dict[str, str] = {}
    findings = {pid: find_sensitive(text, red.rules, red.vault) for pid, text in snap.parent_texts.items()}
    for e in snap.elements:
        piece = e.text.strip()
        if not piece:
            continue
        parent_text = snap.parent_texts.get(e.parent, "")
        f = next((f for f in findings.get(e.parent, []) if piece in parent_text[f.start:f.end]), None)
        if f:
            hidden[e.id] = red.note(f.type, f.value, f.reason, f.source, hint_for(f, red.rules))
    return hidden


def _clean(e: Element, fixed: dict[str, str], split: str, red: _Redactor) -> Element:
    text = fixed.get("text") or red.text(e.text)
    if text == e.text and split:
        text = split
    value = fixed.get("value") or red.text(e.value)
    return replace(e, text=text, label=red.text(e.label), value=value, selector="")


def sanitize(snap: Snapshot, vault: Vault, rules: Rules) -> SanitizedSnapshot:
    red = _Redactor(vault, rules)
    # Register structural values first so every later mention of them, such as an image alt text, is hidden too.
    fixed = {e.id: _structural_placeholder(e, red, rules) for e in snap.elements}
    split = _split_placeholders(snap, red)
    elements = [_clean(e, fixed[e.id], split.get(e.id, ""), red) for e in snap.elements]
    changed = {e.id for e, c in zip(snap.elements, elements) if (e.text, e.label, e.value) != (c.text, c.label, c.value)}
    boxes = _sensitive_boxes(snap, rules, changed)
    page_text = snap.page_text if snap.visible_text is None else snap.visible_text
    return SanitizedSnapshot(
        url=red.text(unquote_plus(snap.url)),
        elements=elements,
        page_text=red.text(page_text),
        aria=red.text(snap.aria),
        screenshot=_blackout(snap.screenshot, boxes),
        report=list(red.report.values()),
        element_types={e.id: e.sensitive_type for e in snap.elements if e.sensitive_type},
        boxes=boxes,
    )
