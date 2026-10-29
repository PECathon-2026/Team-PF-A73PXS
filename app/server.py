import asyncio
import json
import os
import re
import socket
import subprocess
import sys
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from playwright.async_api import async_playwright

from app import agent
from app.rules import ALL_TYPES, Rules, load_rules, save_rules
from app.runner import task_for

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.getenv("PRIVACYLENS_PORT", "8000"))
LOOPBACK_CLIENTS = {"127.0.0.1", "::1", "localhost"}
LOOPBACK_NAMES = {"localhost", "127.0.0.1", "[::1]"}
RULE_CHECK_SECONDS = 2
# A rule that takes exponential time on one of these would freeze every snapshot, so it is refused.
RULE_PROBES = [c * 40 + "!" for c in "aA1 .-_@x"]
PROBE_SCRIPT = "import re, sys; rx = re.compile(sys.argv[1]); [rx.search(s) for s in sys.argv[2:]]"
TITLES = {"checkout": "Pay for my cart", "login": "Log me in", "support": "Ask support", "video": "Mute the call",
          "developer": "Developer settings", "injection": "Leave feedback"}

load_dotenv(ROOT / ".env")


class State:
    session: agent.Session | None = None
    run_task: asyncio.Task | None = None
    rules: Rules = load_rules()
    ai: str = "gemini" if os.getenv("GEMINI_API_KEY") else "mock"


state = State()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_playwright() as pw:
        # Proxy-only WebRTC is a second lock behind the init script that removes WebRTC from pages.
        app.state.browser = await pw.chromium.launch(args=["--force-webrtc-ip-handling-policy=disable_non_proxied_udp"])
        yield
        if state.session:
            await state.session.close()
        await app.state.browser.close()


app = FastAPI(lifespan=lifespan)


def _png_size(png: bytes) -> list[int]:
    return list(Image.open(BytesIO(png)).size) if png else [0, 0]


def _lan_addresses() -> set[str]:
    try:
        return set(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        return set()


LAN_ADDRESSES = _lan_addresses()


def _host_name(request: Request) -> str:
    host = request.headers.get("host", "")
    return host.rsplit(":", 1)[0] if not host.endswith("]") else host


@app.middleware("http")
async def trusted_host(request: Request, call_next):
    """A web page elsewhere cannot rename itself to our address (DNS rebinding) and read the API."""
    if request.url.path.startswith("/api/") and _host_name(request) not in LOOPBACK_NAMES | LAN_ADDRESSES:
        return Response("unknown host", status_code=403)
    return await call_next(request)


def local_only(request: Request) -> None:
    """Phones may watch the AI view and approve; settings, runs and raw page data stay on this machine."""
    client = request.client.host if request.client else ""
    if client not in LOOPBACK_CLIENTS or _host_name(request) not in LOOPBACK_NAMES:
        raise HTTPException(403, "only available on the computer running PrivacyLens")


@app.get("/api/scenarios")
def scenarios():
    return [{"key": k, "title": TITLES[k], "task": task_for(k)} for k in agent.SCENARIO_FILES]


@app.get("/api/config")
def config():
    return {"ai": state.ai, "gemini_available": bool(os.getenv("GEMINI_API_KEY")), "types": ALL_TYPES}


@app.post("/api/config")
def set_ai(request: Request, body: dict = Body(...)):
    local_only(request)
    if body.get("ai") == "gemini" and not os.getenv("GEMINI_API_KEY"):
        return {"ok": False, "error": "No Gemini key found in .env"}
    state.ai = body["ai"]
    return {"ok": True, "ai": state.ai}


@app.post("/api/session")
async def start_session(request: Request, body: dict = Body(...)):
    local_only(request)
    if state.session:
        await state.session.close()
    s = agent.Session(body["scenario"], body.get("task") or task_for(body["scenario"]), state.ai, state.rules)
    await s.start(app.state.browser, f"http://127.0.0.1:{PORT}")
    state.session = s
    state.run_task = asyncio.create_task(agent.run(s))
    return {"id": s.id}


@app.get("/api/session")
def session_state():
    s = state.session
    if s is None:
        return {"id": None}
    return {
        "id": s.id, "scenario": s.scenario, "task": s.task, "status": s.status, "narration": s.narration,
        "success": s.success, "approval": s.approval, "size": _png_size(s.real_png), "boxes": s.boxes,
        "hidden": [vars(r) for r in s.report.values()], "blocked": s.blocked,
        "events": [vars(e) for e in s.events], "ai": s.llm.name,
    }


@app.get("/api/session/inspect")
def inspect(request: Request):
    local_only(request)
    s = state.session
    if s is None:
        return {}
    return {"raw": s.raw_text[:4000], "outbound": s.outbound, "history": s.history}


@app.get("/api/session/image/{kind}")
def image(request: Request, kind: str):
    if kind == "real":
        local_only(request)
    s = state.session
    png = (s.real_png if kind == "real" else s.ai_png) if s else b""
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.post("/api/session/approve")
def approve(body: dict = Body(...)):
    return {"accepted": bool(state.session and state.session.answer(bool(body.get("approved"))))}


@app.post("/api/leak-test")
async def leak_test(request: Request):
    local_only(request)
    if state.session is None:
        await start_session(request, {"scenario": "checkout"})
        await asyncio.sleep(0.5)
    return {"blocked": await agent.leak_test(state.session)}


def _check_pattern(pattern: str) -> None:
    if len(pattern) > 100:
        raise HTTPException(400, "That rule is too long.")
    try:
        re.compile(pattern)
    except re.error:
        raise HTTPException(400, "That rule is not a valid pattern.") from None
    if not _pattern_is_fast(pattern):
        raise HTTPException(400, "That rule is too slow to check pages with.")


def _pattern_is_fast(pattern: str) -> bool:
    """Try the rule in a separate process, which can be killed if it never finishes."""
    try:
        subprocess.run([sys.executable, "-c", PROBE_SCRIPT, pattern, *RULE_PROBES], timeout=RULE_CHECK_SECONDS,
                       check=True, capture_output=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False
    return True


@app.get("/api/rules")
def get_rules():
    return state.rules.to_dict()


@app.put("/api/rules")
def put_rules(request: Request, body: dict = Body(...)):
    local_only(request)
    for pattern in body.get("custom", []):
        _check_pattern(pattern)
    state.rules.enabled.update(body.get("enabled", {}))
    state.rules.hints = body.get("hints", state.rules.hints)
    state.rules.custom = [c for c in body.get("custom", state.rules.custom) if c.strip()]
    save_rules(state.rules)
    return state.rules.to_dict()


@app.get("/api/eval")
def eval_results():
    path = ROOT / "eval" / "results.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@app.post("/api/eval/run")
async def run_eval(request: Request):
    local_only(request)
    proc = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / "eval" / "run_eval.py"), "--quick",
                                                cwd=str(ROOT))
    await proc.wait()
    return eval_results()


app.mount("/scenarios", StaticFiles(directory=ROOT / "scenarios"), name="scenarios")
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
