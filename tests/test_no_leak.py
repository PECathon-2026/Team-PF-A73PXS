import asyncio
import json
import re
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from app import agent
from app.llm import MockLLM
from app.profile import ANNOTATIONS_PATH
from app.runner import run_scenario

ANNOTATIONS = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))["scenarios"]
NOT_TEXT = {"FACE", "MEETING_LINK", "INJECTION"}


def compact(s: str) -> str:
    return re.sub(r"[\s\-.]", "", s).lower()


def secrets_for(scenario: str) -> list[str]:
    ann = ANNOTATIONS[Path(agent.SCENARIO_FILES[scenario]).stem]
    values = [i["value"] for i in ann["sensitive"] if i["type"] not in NOT_TEXT and i["location"] != "input"]
    return values + ann["canaries"]


async def _payloads(base_url: str, scenario: str, llm=None) -> list[str]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        session = await run_scenario(browser, base_url, scenario, llm=llm)
        await session.close()
        await browser.close()
    return session.llm.payloads


@pytest.mark.parametrize("scenario", agent.SCENARIO_FILES)
def test_no_annotated_value_reaches_the_ai(base_url, scenario):
    payloads = asyncio.run(_payloads(base_url, scenario))
    assert payloads
    for value in secrets_for(scenario):
        assert not any(value in p or compact(value) in compact(p) for p in payloads), value


def test_profile_values_never_reach_the_ai_even_with_a_gullible_model(base_url):
    payloads = asyncio.run(_payloads(base_url, "injection", llm=MockLLM(gullible=True)))
    profile = json.loads((Path(__file__).resolve().parent.parent / "config" / "user_profile.fake.json").read_text())
    for value in (profile["card"]["number"], profile["card"]["cvv"], profile["password"], profile["email"]):
        assert not any(value in p for p in payloads)
