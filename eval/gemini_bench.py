"""Throwaway Gemini benchmark: runs every scenario N times and reports successes and failure details.
Never prints the API key: only status codes, model names and parsed action names are logged."""
import asyncio
import collections
import functools
import http.server
import json
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Admin\Documents\PrivacyLens")
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import httpx  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

from app import agent  # noqa: E402
from app.runner import run_scenario  # noqa: E402

CALLS: list[dict] = []
_real_post = httpx.post


def logged_post(url, *args, **kwargs):
    model = str(url).split("/models/")[1].split(":")[0]
    start = time.monotonic()
    entry = {"model": model}
    try:
        r = _real_post(url, *args, **kwargs)
    except Exception as exc:
        entry.update(status=type(exc).__name__, secs=round(time.monotonic() - start, 1))
        CALLS.append(entry)
        raise
    entry.update(status=r.status_code, secs=round(time.monotonic() - start, 1))
    if r.status_code == 200:
        try:
            cand = r.json()["candidates"][0]
            text = cand["content"]["parts"][-1]["text"]
            entry["finish"] = cand.get("finishReason")
            try:
                entry["action"] = json.loads(text).get("action")
            except Exception:
                entry["action"] = "UNPARSABLE:" + text[:60].replace("\n", " ")
        except Exception as exc:
            entry["action"] = f"NO_TEXT:{type(exc).__name__}"
    else:
        entry["retry_after"] = r.headers.get("retry-after")
        delay = re.search(r'"retryDelay":\s*"([^"]+)"', r.text)
        entry["retry_delay"] = delay[1] if delay else None
        quota = re.search(r'"quotaId":\s*"([^"]+)"', r.text)
        entry["quota"] = quota[1] if quota else None
    CALLS.append(entry)
    return r


httpx.post = logged_post


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


async def main(repeats: int) -> None:
    server = serve()
    base = f"http://127.0.0.1:{server.server_port}"
    wins = collections.Counter()
    runs = collections.Counter()
    statuses = collections.Counter()
    t0 = time.monotonic()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for rep in range(repeats):
            for key in agent.SCENARIO_FILES:
                first = len(CALLS)
                session = await run_scenario(browser, base, key, llm_name="gemini")
                calls = CALLS[first:]
                runs[key] += 1
                wins[key] += bool(session.success)
                for c in calls:
                    statuses[(c["model"], c["status"])] += 1
                models = sorted({c["model"] for c in calls if c["status"] == 200})
                line = f"[{rep + 1}] {key}: {'OK' if session.success else 'FAIL'} calls={len(calls)} models={models}"
                print(line, flush=True)
                if not session.success:
                    print("    narration:", session.narration, flush=True)
                    for h in session.history:
                        print("    hist:", h["step"], h["action"], h["result"][:110], flush=True)
                    for c in calls:
                        print("    call:", c, flush=True)
                await session.close()
        await browser.close()
    server.shutdown()
    total = sum(wins.values())
    n = sum(runs.values())
    print(f"\nTOTAL {total}/{n} = {100 * total / n:.1f}%  in {time.monotonic() - t0:.0f}s")
    for key in agent.SCENARIO_FILES:
        print(f"  {key}: {wins[key]}/{runs[key]}")
    print("HTTP outcomes per (model, status):", dict(statuses))


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 4))
