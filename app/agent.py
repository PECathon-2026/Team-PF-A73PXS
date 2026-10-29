import asyncio
import re
import uuid

from app.dom_snapshot import take_snapshot
from app.executor import block_external, execute
from app.guard import check_outbound
from app.llm import LLMError, RecordingLLM, get_llm
from app.models import Action, AuditEvent, ReportItem
from app.profile import load_canaries_into_vault, load_profile_into_vault
from app.prompts import SYSTEM_PROMPT, build_observation
from app.rules import Rules
from app.sanitizer import sanitize
from app.scrub import scrub
from app.validator import parse_action, validate
from app.vault import Vault

STEP_BUDGET = 12
MAX_REJECTIONS = 3
APPROVAL_SECONDS = 120
SCENARIO_FILES = {
    "checkout": "01_checkout.html", "login": "02_login_otp.html", "support": "03_support_chat.html",
    "video": "04_video_call.html", "developer": "05_dev_settings.html", "injection": "06_injection.html",
}
SECRET_WORDS = {"CARD": "card number", "CVV": "card security code", "PASSWORD": "password", "OTP": "one-time code"}


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
        self.boxes: list = []
        self.rejections = 0
        self.approval: dict | None = None
        self.approval_answer: bool | None = None
        self._answered = asyncio.Event()
        self._approved_groups: set[str] = set()
        self.page = self.context = None

    def emit(self, step: int, kind: str, detail: str) -> None:
        self.events.append(AuditEvent(step, kind, scrub(detail, self.vault)))

    def block(self, step: int, reason: str) -> None:
        self.blocked.append(reason)
        self.emit(step, "block", reason)

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


def _question(action: Action, label: str, raw_text: str, vault: Vault, kind: str) -> tuple[str, str]:
    if kind in SECRET_WORDS and action.action == "type":
        return f"Use your saved {SECRET_WORDS[kind]} for \"{label}\"?", "It fills in private details that stay on this device."
    amount = re.search(r"(?:Rs\.?|INR)\s?[\d,]+", raw_text)
    card = next((v for t, v, _ in vault.items() if t == "CARD"), "")
    if re.search(r"\bpay\b", label, re.I):
        parts = [f"Pay {amount.group()}" if amount else "Pay", f"with your card ending {card[-4:]}" if card else ""]
        return " ".join(p for p in parts if p) + "?", "Paying cannot be undone."
    return f"Go ahead and press \"{label}\"?", "This kind of step cannot easily be undone."


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
    session.emit(n, "llm", "the AI answered")
    action = parse_action(reply)
    result = validate(action, san, session.vault) if action else None
    if action is None or not result.ok:
        reason = result.reason if result else "The reply was not valid JSON."
        session.history.append({"step": n, "action": getattr(action, "action", "?"), "label": "", "value": "",
                                "result": f"rejected: {reason}"})
        session.emit(n, "validate", f"rejected: {reason}")
        session.rejections += 1
        return "too many rejected actions" if session.rejections >= MAX_REJECTIONS else ""
    session.rejections = 0
    if action.action == "done":
        return "done"
    return await _act(session, n, action, result, raw, san)


async def _act(session: Session, n: int, action: Action, result, raw, san) -> str:
    element = next((e for e in raw.elements if e.id == action.target), None)
    label = (element.label or element.text) if element else ""
    kind = san.element_types.get(action.target, "")
    group = "payment" if kind in {"CARD", "CVV"} else kind
    session.narration = f"Working on \"{label}\"..." if label else "Thinking..."
    if result.needs_approval and group not in session._approved_groups:
        question, why = _question(action, label, raw.page_text, session.vault, kind)
        session.emit(n, "approval", "asked the user")
        if not await session.ask(question, why):
            session.emit(n, "approval", "not approved")
            return "stopped by you"
        session._approved_groups.add(group)
    await execute(session.page, action, raw, session.vault)
    session.history.append({"step": n, "action": action.action, "label": label, "value": action.value, "result": "ok"})
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
            reason = "blocked"
        if reason:
            break
    session.success = await _check_success(session)
    session.status = "blocked" if reason == "blocked" else "done"
    session.narration = "Done." if session.success else f"Stopped: {reason}."
    session.emit(0, "end", session.narration)


async def _check_success(session: Session) -> bool:
    data = await session.page.evaluate("({done: document.body.dataset.done, leak: document.body.dataset.leak})")
    return data["done"] == "true" and data["leak"] != "true"


async def leak_test(session: Session) -> bool:
    """Send a raw page, canary included, past the sanitizer. The guard must stop it."""
    canary = sorted(session.vault.canaries)[0]
    verdict = check_outbound(f"Leak test payload {canary}", session.vault, session.rules)
    if not verdict.allowed:
        session.block(0, "leak test: " + verdict.reason)
    return not verdict.allowed
