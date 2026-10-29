"""Abort a commit if the staged diff contains something that looks like a real secret."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.detectors import find_sensitive  # noqa: E402

ALLOWED_PREFIXES = ("scenarios/", "tests/", "eval/", "config/user_profile.fake.json", "docs/")
SECRET_TYPES = {"CARD", "AADHAAR", "PAN", "API_KEY"}


def staged_files() -> list[str]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line]


def main() -> int:
    bad = []
    for name in staged_files():
        if name.startswith(ALLOWED_PREFIXES):
            continue
        if name == ".env":
            bad.append((name, "env file"))
            continue
        text = subprocess.run(["git", "show", f":{name}"], capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout
        bad += [(name, f.type) for f in find_sensitive(text) if f.type in SECRET_TYPES and f.source == "pattern"]
    for name, kind in bad:
        print(f"blocked: {kind} in {name}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
