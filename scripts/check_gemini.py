"""Send one harmless request to Gemini and report whether it worked. Never prints the key."""
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
MODELS = ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.8-flash"]


def try_model(key: str, model: str) -> bool:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": "Reply with the single word: ok"}]}]}
    try:
        r = httpx.post(url, headers={"x-goog-api-key": key}, json=body, timeout=60)
    except httpx.HTTPError as exc:
        print(f"{model}: network problem ({type(exc).__name__})")
        return False
    if r.status_code == 200:
        print(f"{model}: works")
        return True
    message = r.json().get("error", {}).get("message", "")[:120].replace(key, "[key]")
    print(f"{model}: HTTP {r.status_code} {message}")
    return False


def main() -> int:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        print("No GEMINI_API_KEY in .env")
        return 1
    chosen = [os.getenv("GEMINI_MODEL")] if os.getenv("GEMINI_MODEL") else MODELS
    working = [m for m in chosen if try_model(key, m)]
    if working:
        print(f"Put this in .env:  GEMINI_MODEL={working[0]}")
        return 0
    print("No model answered. Wait a few minutes and run this again.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
