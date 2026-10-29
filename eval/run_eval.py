"""Measure PrivacyLens against the annotated fake pages. Writes eval/results.json and eval/results.md."""
import argparse
import asyncio
import functools
import http.server
import json
import os
import platform
import statistics
import sys
import threading
import time
import tracemalloc
from pathlib import Path

import psutil
from dotenv import load_dotenv
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from app import agent  # noqa: E402
from app.detectors import compact, compact_value  # noqa: E402
from app.dom_snapshot import take_snapshot  # noqa: E402
from app.guard import check_outbound  # noqa: E402
from app.llm import MockLLM  # noqa: E402
from app.models import SanitizedSnapshot  # noqa: E402
from app.profile import load_canaries_into_vault, load_profile_into_vault  # noqa: E402
from app.prompts import SYSTEM_PROMPT, build_observation  # noqa: E402
from app.rules import Rules  # noqa: E402
from app.runner import run_scenario  # noqa: E402
from app.sanitizer import sanitize  # noqa: E402
from app.validator import parse_action, validate  # noqa: E402
from app.vault import Vault  # noqa: E402

ANNOTATIONS = json.loads((ROOT / "scenarios" / "annotations.json").read_text(encoding="utf-8"))["scenarios"]
ADVERSARIAL = json.loads((Path(__file__).with_name("adversarial_cases.json")).read_text(encoding="utf-8"))
NOT_TEXT = {"FACE", "CANARY", "MEETING_LINK", "INJECTION"}


def blob_of(san: SanitizedSnapshot) -> str:
    parts = [san.page_text, san.aria, san.url]
    parts += [f"{e.text} {e.label} {e.value}" for e in san.elements]
    return " ".join(parts)


def present(value: str, blob: str) -> bool:
    return value in blob or compact_value(value) in compact(blob)[0]


def pct(n: float, d: float) -> float:
    return round(100 * n / d, 1) if d else 100.0


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def fresh_vault() -> Vault:
    vault = Vault()
    load_profile_into_vault(vault)
    load_canaries_into_vault(vault)
    return vault


async def open_page(browser, base_url: str, key: str):
    page = await browser.new_page(viewport={"width": 1100, "height": 800})
    await page.goto(f"{base_url}/scenarios/{agent.SCENARIO_FILES[key]}")
    return page


def raw_as_sanitized(raw) -> SanitizedSnapshot:
    return SanitizedSnapshot(raw.url, raw.elements, raw.page_text, raw.aria, b"", [])


async def detection_and_leakage(browser, base_url: str) -> dict:
    per_type: dict[str, list[int]] = {}
    lookalikes = redacted_lookalikes = 0
    exposed_without = exposed_with = 0
    for key, file in agent.SCENARIO_FILES.items():
        ann = ANNOTATIONS[Path(file).stem]
        page = await open_page(browser, base_url, key)
        vault, rules = fresh_vault(), Rules()
        raw = await take_snapshot(page, rules, vault)
        san = sanitize(raw, vault, rules)
        raw_blob, safe_blob = blob_of(raw_as_sanitized(raw)), blob_of(san)
        for item in ann["sensitive"]:
            if item["type"] in NOT_TEXT or item["location"] == "input" or not present(item["value"], raw_blob):
                continue
            hidden = not present(item["value"], safe_blob)
            stats = per_type.setdefault(item["type"], [0, 0])
            stats[0] += hidden
            stats[1] += 1
            exposed_without += 1
            exposed_with += not hidden
        for look in ann["lookalikes"]:
            if present(look["value"], raw_blob):
                lookalikes += 1
                redacted_lookalikes += not present(look["value"], safe_blob)
        await page.close()
    found = sum(h for h, _ in per_type.values())
    total = sum(n for _, n in per_type.values())
    return {
        "recall_overall_pct": pct(found, total),
        "recall_by_type_pct": {t: pct(h, n) for t, (h, n) in sorted(per_type.items())},
        "items_checked": total,
        "precision_pct": pct(found, found + redacted_lookalikes),
        "lookalikes_checked": lookalikes,
        "lookalikes_wrongly_hidden": redacted_lookalikes,
        "baseline": {"secrets_exposed_without_privacylens": exposed_without, "secrets_exposed_with": exposed_with},
    }


def secrets_in(payloads: list[str], key: str) -> list[str]:
    ann = ANNOTATIONS[Path(agent.SCENARIO_FILES[key]).stem]
    values = [i["value"] for i in ann["sensitive"] if i["type"] not in NOT_TEXT] + ann["canaries"]
    return [v for v in values if any(present(v, p) for p in payloads)]


async def task_runs(browser, base_url: str, llm_name: str = "mock") -> dict:
    results, leaks, timings = {}, [], []
    for key in agent.SCENARIO_FILES:
        start = time.perf_counter()
        session = await run_scenario(browser, base_url, key, llm_name=llm_name)
        steps = max(1, len([e for e in session.events if e.kind == "execute"]))
        timings.append((time.perf_counter() - start) * 1000 / steps)
        leaks += secrets_in(session.llm.payloads, key)
        blocked = [b for b in session.blocked if b.startswith("blocked a request")]
        results[key] = {"success": bool(session.success), "steps": steps, "blocked_requests": len(blocked)}
        await session.close()
    return {"scenarios": results, "task_success_pct": pct(sum(r["success"] for r in results.values()), len(results)),
            "leaked_values_in_ai_payloads": len(leaks), "step_ms": timings}


async def injection_and_adversarial(browser, base_url: str) -> dict:
    session = await run_scenario(browser, base_url, "injection", llm=MockLLM(gullible=True))
    rejected = [h for h in session.history if h["result"].startswith("rejected")]
    leaked = await session.page.evaluate("document.body.dataset.leak") == "true"
    attack = {"card_pasted_into_feedback": leaked,
              "attempts_rejected_by_validator": len(rejected), "task_still_ok_or_stopped": session.status}
    await session.close()
    page = await open_page(browser, base_url, "checkout")
    vault, rules = fresh_vault(), Rules()
    san = sanitize(await take_snapshot(page, rules, vault), vault, rules)
    cases = [text_case(c, rules) for c in ADVERSARIAL["text"]]
    cases += [hostile_case(c, san, vault) for c in ADVERSARIAL["hostile_replies"]]
    cases.append(await fail_closed_case(browser, base_url))
    await page.close()
    return {"injection": attack, "cases": cases, "passed": sum(c["pass"] for c in cases), "total": len(cases)}


def text_case(case: dict, rules: Rules) -> dict:
    from app.detectors import find_sensitive
    types = [f.type for f in find_sensitive(case["text"], rules)]
    return {"name": case["name"], "pass": case["expect"] in types}


def hostile_case(case: dict, san: SanitizedSnapshot, vault: Vault) -> dict:
    reply = case["reply"]
    for e in san.elements:
        reply = reply.replace("@" + e.label.lower().replace(" ", "_"), e.id)
    action = parse_action(reply)
    ok = action is not None and validate(action, san, vault).ok
    return {"name": case["name"], "pass": not ok}


async def fail_closed_case(browser, base_url: str) -> dict:
    original = agent.sanitize
    agent.sanitize = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("forced"))
    try:
        session = await run_scenario(browser, base_url, "checkout")
    finally:
        agent.sanitize = original
    await session.close()
    return {"name": "exception during sanitize sends nothing", "pass": not session.llm.payloads and bool(session.blocked)}


async def guard_baseline(browser, base_url: str) -> dict:
    page = await open_page(browser, base_url, "checkout")
    vault, rules = fresh_vault(), Rules()
    raw = await take_snapshot(page, rules, vault)
    raw_payload = SYSTEM_PROMPT + build_observation("pay", raw_as_sanitized(raw), vault, [])
    await page.close()
    return {"raw_page_blocked_by_guard": not check_outbound(raw_payload, vault, rules).allowed}


async def performance(browser, base_url: str, repeats: int) -> dict:
    t = {"snapshot": [], "detect": [], "sanitize": [], "guard": []}
    from app.detectors import find_sensitive
    for key in agent.SCENARIO_FILES:
        page = await open_page(browser, base_url, key)
        for _ in range(repeats):
            vault, rules = fresh_vault(), Rules()
            s = time.perf_counter()
            raw = await take_snapshot(page, rules, vault)
            t["snapshot"].append((time.perf_counter() - s) * 1000)
            s = time.perf_counter()
            find_sensitive(raw.page_text, rules, vault)
            t["detect"].append((time.perf_counter() - s) * 1000)
            s = time.perf_counter()
            san = sanitize(raw, vault, rules)
            t["sanitize"].append((time.perf_counter() - s) * 1000)
            payload = SYSTEM_PROMPT + build_observation("task", san, vault, [])
            s = time.perf_counter()
            check_outbound(payload, vault, rules)
            t["guard"].append((time.perf_counter() - s) * 1000)
        await page.close()
    return t


def summarize(values: list[float]) -> dict:
    ordered = sorted(values)
    return {"median_ms": round(statistics.median(ordered), 1),
            "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 1)}


GEMINI_REPEATS = 3


async def gemini_runs(pw, base_url: str, quick: bool) -> dict:
    if quick or not os.getenv("GEMINI_API_KEY"):
        return {"skipped": "quick mode" if quick else "no GEMINI_API_KEY in .env"}
    browser = await pw.chromium.launch()
    wins: dict[str, int] = {}
    failures: list[str] = []
    leaked = 0
    try:
        for _ in range(GEMINI_REPEATS):
            for key in agent.SCENARIO_FILES:
                session = await run_scenario(browser, base_url, key, llm_name="gemini")
                wins[key] = wins.get(key, 0) + bool(session.success)
                leaked += len(secrets_in(session.llm.payloads, key))
                if not session.success:
                    failures.append(f"{key}: {session.narration}")
                await session.close()
    finally:
        await browser.close()
    total = GEMINI_REPEATS * len(wins)
    return {"model": os.getenv("GEMINI_MODEL", ""), "runs_per_scenario": GEMINI_REPEATS,
            "task_success_pct": pct(sum(wins.values()), total), "successes_by_scenario": wins,
            "failure_reasons": failures, "leaked_values_in_ai_payloads": leaked}


async def cross_browser(pw, base_url: str) -> dict:
    out = {}
    for name in ("chromium", "firefox", "webkit"):
        try:
            browser = await getattr(pw, name).launch()
            runs = await task_runs(browser, base_url)
            out[name] = {"task_success_pct": runs["task_success_pct"], "leaks": runs["leaked_values_in_ai_payloads"]}
            await browser.close()
        except Exception as exc:
            out[name] = {"skipped": f"{type(exc).__name__}: {str(exc).splitlines()[0][:100]}"}
    return out


def write_markdown(r: dict) -> None:
    d, t, s = r["detection"], r["tasks"], r["security"]
    lines = ["# PrivacyLens evaluation", "", f"Run on {r['machine']['platform']}, mode: {r['mode']}.", "",
             "| Measure | Result |", "|---|---|",
             f"| PII recall | {d['recall_overall_pct']}% of {d['items_checked']} annotated values |",
             f"| Redaction precision | {d['precision_pct']}% ({d['lookalikes_wrongly_hidden']} of "
             f"{d['lookalikes_checked']} lookalikes wrongly hidden) |",
             f"| Exposed without PrivacyLens | {d['baseline']['secrets_exposed_without_privacylens']} values |",
             f"| Exposed with PrivacyLens | {d['baseline']['secrets_exposed_with']} values |",
             f"| Leaked into AI payloads | {t['leaked_values_in_ai_payloads']} across {len(t['scenarios'])} scenarios |",
             f"| Task success (Mock) | {t['task_success_pct']}% |",
             f"| Adversarial cases | {s['passed']} of {s['total']} pass |", "",
             "Recall by type:", ""]
    lines += [f"- {k}: {v}%" for k, v in d["recall_by_type_pct"].items()]
    lines += ["", "Latency (ms):", ""] + [f"- {k}: median {v['median_ms']}, p95 {v['p95_ms']}"
                                          for k, v in r["performance"].items()]
    lines += ["", f"Resources: {json.dumps(r['resources'])}", "", f"Gemini: {json.dumps(r['gemini'])}", "",
              f"Cross-browser: {json.dumps(r.get('cross_browser', 'skipped in quick mode'))}"]
    Path(__file__).with_name("results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main(quick: bool) -> dict:
    tracemalloc.start()
    server, base_url = serve()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        detection = await detection_and_leakage(browser, base_url)
        tasks = await task_runs(browser, base_url)
        security = await injection_and_adversarial(browser, base_url)
        security["raw_page_blocked_by_guard"] = (await guard_baseline(browser, base_url))["raw_page_blocked_by_guard"]
        timings = await performance(browser, base_url, 2 if quick else 5)
        timings["full_step"] = tasks["step_ms"]
        await browser.close()
        cross = None if quick else await cross_browser(pw, base_url)
        gemini = await gemini_runs(pw, base_url, quick)
    server.shutdown()
    del tasks["step_ms"]
    proc = psutil.Process(os.getpid())
    results = {
        "mode": "quick" if quick else "full",
        "machine": {"platform": platform.platform(), "cpus": os.cpu_count(),
                    "ram_gb": round(psutil.virtual_memory().total / 2**30, 1), "python": platform.python_version()},
        "detection": detection, "tasks": tasks, "security": security,
        "performance": {k: summarize(v) for k, v in timings.items()},
        "resources": {"peak_python_mb": round(tracemalloc.get_traced_memory()[1] / 2**20, 1),
                      "process_rss_mb": round(proc.memory_info().rss / 2**20, 1)},
        "gemini": gemini,
    }
    if cross is not None:
        results["cross_browser"] = cross
    (Path(__file__).with_name("results.json")).write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_markdown(results)
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="Mock on Chromium only")
    out = asyncio.run(main(ap.parse_args().quick))
    print(json.dumps({k: out[k] for k in ("detection", "tasks")}, indent=1)[:1500])
