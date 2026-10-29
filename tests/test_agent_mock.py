import asyncio

import pytest
from playwright.async_api import async_playwright

from app.agent import SCENARIO_FILES
from app.llm import MockLLM
from app.runner import run_scenario

SOLVABLE = [s for s in SCENARIO_FILES if s != "injection"]


async def _run(base_url: str, scenario: str):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        session = await run_scenario(browser, base_url, scenario)
        await session.close()
        await browser.close()
    return session


@pytest.mark.parametrize("scenario", SCENARIO_FILES)
def test_mock_completes_scenario(base_url, scenario):
    session = asyncio.run(_run(base_url, scenario))
    assert session.success, [(e.kind, e.detail) for e in session.events]


def test_each_secret_goes_into_its_own_field(base_url):
    session = asyncio.run(_run(base_url, "checkout"))
    typed = {h["label"]: h["value"] for h in session.history if h["action"] == "type"}
    assert typed["CVV"] == "{{CVV#1}}"
    assert typed["Card number"] == "{{CARD#1}}"
    assert typed["Expiry (MM/YY)"] == "{{EXPIRY#1}}"


def test_fooled_ai_is_stopped_on_the_injection_page(base_url):
    async def go():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            session = await run_scenario(browser, base_url, "injection", llm_name="mock_fooled")
            leaked = await session.page.evaluate("document.body.dataset.leak")
            await session.close()
            await browser.close()
        return session, leaked

    session, leaked = asyncio.run(go())
    assert leaked != "true"
    assert sum(h["result"].startswith("rejected") for h in session.history) == 3
    assert "not allowed" in session.narration


class DoneFirst:
    """Says done before doing anything, then behaves like the Mock planner."""

    name = "done-first"

    def __init__(self):
        self.calls = 0
        self.inner = MockLLM()

    def next_action(self, system, observation):
        self.calls += 1
        if self.calls == 1:
            return '{"action": "done", "reason": "looks finished"}'
        return self.inner.next_action(system, observation)


def test_done_before_any_step_is_rejected_and_the_task_still_finishes(base_url):
    async def go():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            session = await run_scenario(browser, base_url, "support", llm=DoneFirst())
            await session.close()
            await browser.close()
        return session

    session = asyncio.run(go())
    assert session.history[0]["result"].startswith("rejected: Nothing has been done yet")
    assert session.success
