"""Abort a commit if the staged diff contains something that looks like a real secret."""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.detectors import find_sensitive  # noqa: E402

# Synthetic test data lives here, so only API keys are looked for; a real key is never fine, even in docs.
SYNTHETIC_PREFIXES = ("scenarios/", "tests/", "eval/", "config/user_profile.fake.json", "docs/", "README.md", "STATUS.md")
# Fake values in this project say so, for example sk-test-FAKEKEY or a user@example.test address.
OBVIOUSLY_FAKE = re.compile(r"fake|test|example|demo|dummy|canary", re.I)
SECRET_TYPES = {"CARD", "AADHAAR", "PAN", "API_KEY"}
ALWAYS_TYPES = {"API_KEY"}


def staged_files() -> list[str]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line]


def main() -> int:
    bad = []
    for name in staged_files():
        if Path(name).name == ".env":
            bad.append((name, "env file"))
            continue
        types = ALWAYS_TYPES if name.startswith(SYNTHETIC_PREFIXES) else SECRET_TYPES
        text = subprocess.run(["git", "show", f":{name}"], capture_output=True, text=True, encoding="utf-8",
                              errors="ignore").stdout
        bad += [(name, f.type) for f in find_sensitive(text)
                if f.type in types and f.source == "pattern" and not OBVIOUSLY_FAKE.search(f.value)]
    for name, kind in bad:
        print(f"blocked: {kind} in {name}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
