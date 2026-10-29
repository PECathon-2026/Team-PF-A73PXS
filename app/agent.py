import asyncio
import re
import traceback
import uuid
from pathlib import Path

from playwright.async_api import Error as PlaywrightError

from app.dom_snapshot import take_snapshot
from app.executor import block_external, execute
from app.guard import check_outbound
from app.llm import LLMError, RecordingLLM, get_llm
from app.models import Action, AuditEvent, ReportItem, SanitizedSnapshot, Snapshot, ValidationResult
from app.profile import load_canaries_into_vault, load_profile_into_vault
from app.prompts import SYSTEM_PROMPT, build_observation
from app.rules import Rules
from app.sanitizer import sanitize
from app.scrub import scrub
from app.validator import parse_action, validate
from app.vault import Vault

STEP_BUDGET = 12
HISTORY_CHARS = 200
MAX_REJECTIONS = 3
APPROVAL_SECONDS = 120
SCENARIO_FILES = {
    "checkout": "01_checkout.html", "login": "02_login_otp.html", "support": "03_support_chat.html",
    "video": "04_video_call.html", "developer": "05_dev_settings.html", "injection": "06_injection.html",
}
HUMAN_FIELD = {"CARD": "your card number", "CVV": "the card security code", "EXPIRY": "the card expiry",
               "PASSWORD": "your password", "OTP": "the one-time code", "EMAIL": "your email", "PHONE": "your phone",
               "NAME": "your name", "ADDRESS": "your address"}
TECHNICAL = re.compile(r"redacted|guard|payload|llm|token", re.I)
TRACE_FRAMES = 3
LEAK_CANARY = "CANARY-LEAKTEST-0"
SECRET_WORDS = {"CARD": "card number", "CVV": "card security code", "PASSWORD": "password", "OTP": "one-time code"}
ASK_FIRST_REJECTED = ("The secrets list and the visible page are everything you get. Take the next visible step "
                      "yourself; ask_user again only if no step can move the task forward.")


class Session:
    def __init__(self, scenario: str, task: str, llm_name: str, rules: Rules) -> None:
        self.id = uuid.uuid4().hex[:8]
        self.scenario, self.task, self.rules = scenario, task, rules
        self.vault = Vault()
        load_profile_into_vault(self.vault)
        load_canaries_into_vault(self.vault)
        self.llm = RecordingLLM(get_llm(llm_name))
        self.events: list[AuditEvent] = []
        self.history: list[dict] = []
        self.report: dict[str, ReportItem] = {}
        self.blocked: list[str] = []
        self.status = "idle"
        self.narration = ""
        self.success: bool | None = None
        self.real_png = self.ai_png = b""
        self.outbound = self.raw_text = ""
        self.boxes: list[tuple[float, float, float, float]] = []
        self.rejections = 0
        self.approval: dict | None = None
        self.approval_answer: bool | None = None
        self._answered = asyncio.Event()
        self.approved_groups: set[str] = set()
        self.page = self.context = None

    def emit(self, step: int, kind: str, detail: str) -> None:
        self.events.append(AuditEvent(step, kind, self._safe(detail)))

    def block(self, step: int, reason: str) -> None:
        reason = self._safe(reason)
        self.blocked.append(reason)
        self.events.append(AuditEvent(step, "block", reason))

    def _safe(self, text: str) -> str:
        try:
            return scrub(text, self.vault)
        except Exception:
            return "[hidden]"

    def answer(self, approved: bool) -> bool:
        """First answer wins, whichever device it comes from."""
        if self.approval is None or self.approval_answer is not None:
            return False
        self.approval_answer = approved
        self._answered.set()
        return True

    async def start(self, browser, base_url: str) -> None:
        self.context = await browser.new_context(viewport={"width": 1100, "height": 800})
        await block_external(self.context, lambda host: self.block(0, f"blocked a request to {host}"))
        self.page = await self.context.new_page()
        await self.page.goto(f"{base_url}/scenarios/{SCENARIO_FILES[self.scenario]}")

    async def close(self) -> None:
        if self.context:
            await self.context.close()
        self.vault.clear()

    async def ask(self, question: str, why: str) -> bool:
        self.approval = {"question": question, "why": why}
        self.approval_answer = None
        self._answered.clear()
        self.status = "waiting"
        try:
            await asyncio.wait_for(self._answered.wait(), APPROVAL_SECONDS)
        except asyncio.TimeoutError:
            return False
        finally:
            self.approval = None
            self.status = "running"
        return bool(self.approval_answer)


def _narration(action: Action, kind: str) -> str:
    if action.action == "type":
        return f"Filling in {HUMAN_FIELD.get(kind, 'a field')}..."
    return "Pressing a button..." if action.action == "click" else "Looking at the page..."


def _question(action: Action, label: str, raw_text: str, vault: Vault, kind: str) -> tuple[str, str]:
    label = TECHNICAL.sub("item", label)
    if kind in SECRET_WORDS and action.action == "type":
        return f"Use your saved {SECRET_WORDS[kind]} for \"{label}\"?", "It fills in private details that stay on this device."
    amount = re.search(r"(?:Rs\.?|INR)\s?[\d,]+", raw_text)
    card = next((v for t, v, _ in vault.items() if t == "CARD"), "")
    if re.search(r"\bpay\b", label, re.I):
        parts = [f"Pay {amount.group()}" if amount else "Pay", f"with your card ending {card[-4:]}" if card else ""]
        return " ".join(p for p in parts if p) + "?", "Paying cannot be undone."
    return f"Go ahead and press \"{label}\"?", "This kind of step cannot easily be undone."


def _check(action: Action | None, san: SanitizedSnapshot, session: Session) -> ValidationResult | None:
    if action is None:
        return None
    if action.action == "done" and not any(h["result"] == "ok" for h in session.history):
        return ValidationResult(False, reason="Nothing has been done yet. Take the steps the task needs first.")
    # The first ask_user goes back to the AI: it usually means a value appears only after a later step.
    if action.action == "ask_user" and not any(h["action"] == "ask_user" for h in session.history):
        return ValidationResult(False, reason=ASK_FIRST_REJECTED)
    return validate(action, san, session.vault)


async def _step(session: Session, n: int) -> str:
    """Run one step. Returns '' to continue, or the reason to stop."""
    raw = await take_snapshot(session.page, session.rules, session.vault)
    san = sanitize(raw, session.vault, session.rules)
    session.real_png, session.ai_png, session.raw_text = raw.screenshot, san.screenshot, raw.page_text
    session.boxes = san.boxes
    session.report.update({r.placeholder: r for r in san.report})
    session.emit(n, "sanitize", f"{len(san.report)} items hidden")

    observation = build_observation(session.task, san, session.vault, session.history)
    session.outbound = SYSTEM_PROMPT + "\n" + observation
    verdict = check_outbound(session.outbound, session.vault, session.rules)
    if not verdict.allowed:
        session.block(n, verdict.reason)
        return "blocked"

    reply = await asyncio.to_thread(session.llm.next_action, SYSTEM_PROMPT, observation)
    session.emit(n, "llm", f"the AI answered ({session.llm.model_used})")
    action = parse_action(reply)
    result = _check(action, san, session)
    if action is None or not result.ok:
        reason = result.reason if result else "The reply was not valid JSON."
        session.history.append({"step": n, "action": getattr(action, "action", "?"), "label": "", "value": "",
                                "result": f"rejected: {reason}"})
        session.emit(n, "validate", f"rejected: {reason}")
        session.rejections += 1
        if session.rejections >= MAX_REJECTIONS:
            return "the AI kept proposing steps that were not allowed, so it was stopped"
        return ""
    session.rejections = 0
    if action.action == "done":
        return "done"
    if action.action == "ask_user":
        session.emit(n, "ask", "the AI asked for help")
        return "the AI needs your help"
    return await _act(session, n, action, result, raw, san)


async def _act(session: Session, n: int, action: Action, result: ValidationResult, raw: Snapshot,
               san: SanitizedSnapshot) -> str:
    element = next((e for e in san.elements if e.id == action.target), None)
    label = (element.label or element.text) if element else ""
    kind = san.element_types.get(action.target, "")
    group = "payment" if kind in {"CARD", "CVV"} else kind
    session.narration = _narration(action, kind)
    remembered = action.action == "type" and group in session.approved_groups
    if result.needs_approval and not remembered:
        question, why = _question(action, label, raw.page_text, session.vault, kind)
        session.emit(n, "approval", "asked the user")
        if not await session.ask(question, why):
            session.emit(n, "approval", "not approved")
            return "stopped by you"
        if action.action == "type":
            session.approved_groups.add(group)
    await execute(session.page, action, raw, session.vault)
    session.history.append({"step": n, "action": action.action, "label": label[:HISTORY_CHARS],
                            "value": action.value[:HISTORY_CHARS], "result": "ok"})
    session.emit(n, "execute", f"{action.action} {label}")
    await session.page.wait_for_timeout(300)
    return ""


async def run(session: Session) -> None:
    session.status = "running"
    reason = "step budget used up"
    for n in range(1, STEP_BUDGET + 1):
        try:
            reason = await _step(session, n)
        except LLMError:
            reason = "the AI could not be reached"
        except Exception as exc:
            session.block(n, f"step failed safely: {type(exc).__name__}")
            session.emit(n, "error", _trace_summary(exc))
            reason = "blocked"
        if reason:
            break
    session.success = await _check_success(session)
    session.status = "blocked" if reason == "blocked" else "done"
    session.narration = "Done." if session.success else f"Stopped: {reason}."
    session.emit(0, "end", session.narration)


def _trace_summary(exc: Exception) -> str:
    """Where the step failed, without the exception message, which can quote page data."""
    frames = traceback.extract_tb(exc.__traceback__)[-TRACE_FRAMES:]
    where = " < ".join(f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in reversed(frames))
    return f"{type(exc).__name__} at {where}"


async def _check_success(session: Session) -> bool:
    if session.page is None:
        return False
    try:
        data = await session.page.evaluate("({done: document.body.dataset.done, leak: document.body.dataset.leak})")
    except PlaywrightError:
        return False
    return data["done"] == "true" and data["leak"] != "true"


def leak_test(session: Session) -> bool:
    """Send a raw page, canary included, past the sanitizer. The guard must stop it.
    The canary lives in a separate vault so it never joins the live session's secrets."""
    probe = Vault()
    probe.canaries.add(LEAK_CANARY)
    verdict = check_outbound(f"Leak test payload {LEAK_CANARY}", probe, session.rules)
    if not verdict.allowed:
        session.block(0, "leak test: " + verdict.reason)
    return not verdict.allowed
