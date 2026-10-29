import asyncio
import json
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import Body, FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from playwright.async_api import async_playwright

from app import agent
from app.rules import ALL_TYPES, Rules, load_rules, save_rules
from app.runner import task_for

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.getenv("PRIVACYLENS_PORT", "8000"))
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
        app.state.browser = await pw.chromium.launch()
        yield
        if state.session:
            await state.session.close()
        await app.state.browser.close()


app = FastAPI(lifespan=lifespan)


def _png_size(png: bytes) -> list[int]:
    return list(Image.open(BytesIO(png)).size) if png else [0, 0]


@app.get("/api/scenarios")
def scenarios():
    return [{"key": k, "title": TITLES[k], "task": task_for(k)} for k in agent.SCENARIO_FILES]


@app.get("/api/config")
def config():
    return {"ai": state.ai, "gemini_available": bool(os.getenv("GEMINI_API_KEY")), "types": ALL_TYPES}


@app.post("/api/config")
def set_ai(body: dict = Body(...)):
    if body.get("ai") == "gemini" and not os.getenv("GEMINI_API_KEY"):
        return {"ok": False, "error": "No Gemini key found in .env"}
    state.ai = body["ai"]
    return {"ok": True, "ai": state.ai}


@app.post("/api/session")
async def start_session(body: dict = Body(...)):
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
def inspect():
    s = state.session
    if s is None:
        return {}
    return {"raw": s.raw_text[:4000], "outbound": s.outbound, "history": s.history}


@app.get("/api/session/image/{kind}")
def image(kind: str):
    s = state.session
    png = (s.real_png if kind == "real" else s.ai_png) if s else b""
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.post("/api/session/approve")
def approve(body: dict = Body(...)):
    return {"accepted": bool(state.session and state.session.answer(bool(body.get("approved"))))}


@app.post("/api/leak-test")
async def leak_test():
    if state.session is None:
        await start_session({"scenario": "checkout"})
        await asyncio.sleep(0.5)
    return {"blocked": await agent.leak_test(state.session)}


@app.get("/api/rules")
def get_rules():
    return state.rules.to_dict()


@app.put("/api/rules")
def put_rules(body: dict = Body(...)):
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
async def run_eval():
    proc = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / "eval" / "run_eval.py"), "--quick",
                                                cwd=str(ROOT))
    await proc.wait()
    return eval_results()


app.mount("/scenarios", StaticFiles(directory=ROOT / "scenarios"), name="scenarios")
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
