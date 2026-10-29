import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "config" / "rules.json"
SCREENS = ROOT / "docs" / "screens"
VIEWPORTS = {"375x812": (375, 812), "1440x900": (1440, 900)}
FORBIDDEN = re.compile(r"redacted|guard|payload|llm|token", re.I)
MAIN_CONTROLS = {"task", "Go", "chip", "switch", "status", "How it works"}

JS_CONTROLS = """() => [...document.querySelectorAll('#main button, #main input, #main a')].map(e => {
  const box = (e.id === 'ai-view' ? e.closest('label') : e).getBoundingClientRect();
  const name = e.id === 'ai-view' ? 'switch' : e.id === 'task' ? 'task' : e.id === 'status' ? 'status'
    : e.classList.contains('chip') ? 'chip' : e.textContent.trim();
  return {name, w: box.width, h: box.height, shown: box.width > 0 && box.height > 0};
}).filter(c => c.shown)"""

JS_COLORS = """() => {
  const bg = getComputedStyle(document.body).backgroundColor;
  const fg = ['body', '.narration', '.task-label'].map(s => getComputedStyle(document.querySelector(s)).color);
  return {bg, fg};
}"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http_json(url, method="GET", body=None):
    import urllib.request
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


@pytest.fixture(scope="session")
def base():
    port = free_port()
    backup = RULES.read_bytes() if RULES.exists() else None
    env = {**os.environ, "PRIVACYLENS_PORT": str(port), "GEMINI_API_KEY": ""}
    proc = subprocess.Popen([sys.executable, "-m", "app.server"], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 60
        while True:
            try:
                http_json(url + "/api/config")
                break
            except Exception:
                if time.time() > deadline or proc.poll() is not None:
                    raise RuntimeError("server did not start")
                time.sleep(0.3)
        yield url
    finally:
        proc.kill()
        proc.wait()
        if backup is None:
            RULES.unlink(missing_ok=True)
        else:
            RULES.write_bytes(backup)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


def open_page(browser, base, size, theme):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, color_scheme=theme)
    page = ctx.new_page()
    page.goto(base)
    page.wait_for_selector(".chip")
    return page


@pytest.fixture(params=[(v, t) for v in VIEWPORTS for t in ("light", "dark")], ids=lambda p: f"{p[0]}-{p[1]}")
def ui(request, browser, base):
    name, theme = request.param
    page = open_page(browser, base, VIEWPORTS[name], theme)
    page.shot = lambda promise: page.screenshot(path=str(SCREENS / f"{promise}_{name}_{theme}.png"))
    page.size_name, page.theme = name, theme
    SCREENS.mkdir(parents=True, exist_ok=True)
    yield page
    page.context.close()


@pytest.fixture
def solo(browser, base):
    SCREENS.mkdir(parents=True, exist_ok=True)
    page = open_page(browser, base, VIEWPORTS["1440x900"], "light")
    yield page
    page.context.close()


def start_run(page, base, title):
    prev = http_json(base + "/api/session").get("id")
    page.get_by_role("button", name=title).click()
    page.get_by_role("button", name="Go").click()
    deadline = time.time() + 20
    while http_json(base + "/api/session").get("id") in (None, prev):
        assert time.time() < deadline, "session did not start"
        time.sleep(0.2)


def finish_run(page, base, approve=None):
    approve = approve or page
    deadline = time.time() + 90
    while time.time() < deadline:
        s = http_json(base + "/api/session")
        if s["status"] in ("done", "blocked"):
            return s
        if s["approval"] and approve.locator("#approval").is_visible():
            approve.locator("#approve").click()
        time.sleep(0.2)
    raise AssertionError("run did not finish")


def run_scenario(page, base, title):
    start_run(page, base, title)
    return finish_run(page, base)


def luminance(rgb):
    chan = [c / 255 for c in rgb]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chan]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def parse_rgb(css):
    return [int(float(n)) for n in re.findall(r"[\d.]+", css)[:3]]


def test_main_screen_shows_only_the_promised_parts(ui):
    controls = ui.evaluate(JS_CONTROLS)
    names = {c["name"] for c in controls}
    assert names == MAIN_CONTROLS, names
    assert sum(c["name"] == "chip" for c in controls) >= 3
    for region in ("#frame", "#status", "#narration", "#task-form", ".switch"):
        assert ui.locator(region).is_visible(), region
    ui.shot("1_main")


def test_switch_toggles_between_real_and_ai_view(ui, base):
    run_scenario(ui, base, "Ask support")
    real, ai = ui.locator("#img-real"), ui.locator("#img-ai")
    ui.wait_for_function("document.getElementById('img-ai').src && document.getElementById('img-real').src")
    assert real.get_attribute("src") != ai.get_attribute("src")
    switch = ui.locator("#ai-view")
    assert switch.get_attribute("role") == "switch" and not switch.is_checked()
    assert "is-shown" in real.get_attribute("class") and "is-shown" not in ai.get_attribute("class")
    ui.locator(".switch").click()
    assert switch.is_checked()
    assert "is-shown" in ai.get_attribute("class") and "is-shown" not in real.get_attribute("class")
    assert ui.evaluate("document.querySelector('img.is-shown').id") == "img-ai"
    ui.shot("2_switch")
    ui.locator(".switch").click()
    assert ui.evaluate("document.querySelector('img.is-shown').id") == "img-real"


def test_human_words_only(ui, base):
    assert not FORBIDDEN.search(ui.inner_text("body"))
    run_scenario(ui, base, "Pay for my cart")
    ui.wait_for_function("document.getElementById('status').textContent.includes('hidden')")
    assert not FORBIDDEN.search(ui.inner_text("body"))
    ui.shot("3_words")


def test_approval_sheet(ui, base):
    start_run(ui, base, "Pay for my cart")
    sheet = ui.locator("#approval .sheet")
    expect(sheet).to_be_visible(timeout=30000)
    question = ui.inner_text("#approval-q").strip()
    assert question and len(re.findall(r"[.?!]", question)) == 1 and "\n" not in question
    assert ui.locator("#approve").bounding_box()["height"] >= 44
    assert ui.locator("#cancel").get_attribute("class") == "quiet"
    assert ui.locator("#why-link").inner_text() == "Why am I asked?"
    box = sheet.bounding_box()
    width, height = VIEWPORTS[ui.size_name]
    if width == 375:
        assert height - (box["y"] + box["height"]) <= 24
    else:
        assert abs((box["x"] + box["width"] / 2) - width / 2) <= 2
    ui.shot("4_approval")
    final = finish_run(ui, base)
    assert final["success"] is True


def test_automatic_light_and_dark(browser, base):
    colors = {}
    for theme in ("light", "dark"):
        page = open_page(browser, base, VIEWPORTS["1440x900"], theme)
        colors[theme] = page.evaluate(JS_COLORS)
        assert not page.get_by_text(re.compile(r"dark mode|light mode|theme", re.I)).count()
        assert not page.locator("[aria-label*=theme i], [id*=theme i]").count()
        page.context.close()
    assert colors["light"]["bg"] != colors["dark"]["bg"]
    for theme, c in colors.items():
        for fg in c["fg"]:
            assert contrast(parse_rgb(fg), parse_rgb(c["bg"])) >= 4.5, (theme, fg, c["bg"])


def test_phone_and_laptop_layout(ui):
    scroll = ui.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert scroll[0] <= scroll[1]
    for c in ui.evaluate(JS_CONTROLS):
        assert c["h"] >= 44 and c["w"] >= 44, c
    ui.shot("6_layout")


def test_phone_can_answer_for_the_laptop(solo, base):
    start_run(solo, base, "Pay for my cart")
    expect(solo.locator("#approval")).to_be_visible(timeout=30000)
    phone = solo.context.new_page()
    phone.set_viewport_size({"width": 375, "height": 812})
    phone.goto(base)
    expect(phone.locator("#approval")).to_be_visible(timeout=10000)
    assert phone.inner_text("#approval-q") == solo.inner_text("#approval-q")
    phone.locator("#approve").click()
    expect(solo.locator("#approval")).to_be_hidden(timeout=10000)
    assert finish_run(solo, base)["success"] is True


def test_status_line_tells_the_truth(ui, base):
    final = run_scenario(ui, base, "Pay for my cart")
    n = len(final["hidden"])
    assert n > 0
    expect(ui.locator("#status")).to_have_text(f"{n} things hidden · nothing private shared")
    ui.shot("8_status")


def test_leak_test_and_stopped_message(solo, base):
    run_scenario(solo, base, "Ask support")
    solo.get_by_role("button", name="How it works").click()
    solo.get_by_role("button", name="Run leak test").click()
    expect(solo.locator(".result")).to_contain_text("Blocked")
    solo.get_by_role("button", name="Back", exact=True).click()
    expect(solo.locator("#status")).to_have_text(re.compile(r"^Stopped 1 unsafe message$"))
    solo.screenshot(path=str(SCREENS / "9_leak_1440x900_light.png"))


def test_injection_does_not_leak_the_card(solo, base):
    final = run_scenario(solo, base, "Leave feedback")
    assert final["success"] is True
    history = http_json(base + "/api/session/inspect")["history"]
    typed = [h for h in history if h["action"] == "type"]
    assert not any("feedback" in h["label"].lower() and re.search(r"card", h["value"], re.I) for h in typed)
    assert not any(re.search(r"\d{4}", h["value"] or "") and "feedback" in h["label"].lower() for h in typed)


def test_user_rules_apply_on_the_next_run(solo, base):
    original = http_json(base + "/api/rules")
    try:
        baseline = run_scenario(solo, base, "Ask support")
        assert any(h["type"] == "EMAIL" for h in baseline["hidden"])
        saved = http_json(base + "/api/rules", "PUT", {"enabled": {"EMAIL": False}, "custom": ["Falcon"]})
        assert saved["enabled"]["EMAIL"] is False and saved["custom"] == ["Falcon"]
        assert http_json(base + "/api/rules")["custom"] == ["Falcon"]
        after = run_scenario(solo, base, "Ask support")
        # Values saved in the profile are always hidden by exact match, so only pattern hits follow the toggle.
        assert not any(h["type"] == "EMAIL" and h["source"] != "context" for h in after["hidden"])
    finally:
        http_json(base + "/api/rules", "PUT", {"enabled": original["enabled"], "hints": original["hints"],
                                                "custom": original["custom"]})


def test_works_offline_with_mock_ai(solo, base):
    assert http_json(base + "/api/config")["ai"] in ("mock", "gemini")
    assert http_json(base + "/api/config")["ai"] == "mock"
    assert http_json(base + "/api/config")["gemini_available"] is False
    final = run_scenario(solo, base, "Pay for my cart")
    assert final["ai"] == "mock" and final["success"] is True


def test_how_it_works_view(solo, base):
    run_scenario(solo, base, "Pay for my cart")
    solo.get_by_role("button", name="How it works").click()
    panel = solo.locator("#how")
    expect(panel).to_be_visible()
    for heading in ("Pipeline for this run", "Raw snapshot", "Outbound text", "Validation and approval decisions",
                    "Evaluation", "Privacy settings", "AI choice"):
        expect(panel).to_contain_text(heading)
    expect(panel.locator(".steps li").first).to_be_visible()
    expect(panel.locator(".mono").first).not_to_be_empty()
    expect(panel.locator(".list li").first).to_contain_text(re.compile("execute|approval|validate"))
    expect(panel.locator(".rules .rule").first).to_be_visible()
    expect(panel.locator("input[name=ai]")).to_have_count(3)
    expect(panel.get_by_role("button", name="Run leak test")).to_be_visible()
    solo.screenshot(path=str(SCREENS / "14_how_1440x900_light.png"))
