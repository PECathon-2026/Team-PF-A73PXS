import asyncio

import pytest
from playwright.async_api import async_playwright

from app.agent import SCENARIO_FILES
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
