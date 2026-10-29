import asyncio
import json
from pathlib import Path

from app.agent import SCENARIO_FILES, Session, run
from app.llm import RecordingLLM
from app.profile import ANNOTATIONS_PATH
from app.rules import Rules


def task_for(scenario: str) -> str:
    stem = Path(SCENARIO_FILES[scenario]).stem
    data = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    return data["scenarios"][stem]["task"]


async def run_scenario(browser, base_url: str, scenario: str, rules: Rules | None = None, llm_name: str = "mock",
                       llm=None, approve: bool | None = True) -> Session:
    """Run one scenario to the end, answering approval prompts automatically when approve is set."""
    session = Session(scenario, task_for(scenario), llm_name, rules or Rules())
    if llm is not None:
        session.llm = RecordingLLM(llm)
    await session.start(browser, base_url)
    task = asyncio.create_task(run(session))
    while not task.done():
        if session.approval is not None and approve is not None:
            session.answer(approve)
        await asyncio.sleep(0.05)
    await task
    return session
