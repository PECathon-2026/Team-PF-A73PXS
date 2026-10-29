"""Entry point of the Windows bundle: PrivacyLens.exe."""
import multiprocessing
import os
import runpy
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

DEFAULT_PORT = 8000
PORT_SEARCH_RANGE = 50
START_TIMEOUT_SECONDS = 60


def run_as_python() -> None:
    """The app starts helper processes with sys.executable, which is this exe when frozen."""
    args = sys.argv[1:]
    if args[0] == "-c":
        sys.argv = ["-c", *args[2:]]
        exec(compile(args[1], "<string>", "exec"), {"__name__": "__main__"})
    else:
        sys.argv = args
        runpy.run_path(args[0], run_name="__main__")


def free_port(start: int) -> int:
    for port in range(start, start + PORT_SEARCH_RANGE):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit(f"No free port between {start} and {start + PORT_SEARCH_RANGE - 1}.")


def lan_address() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("10.255.255.255", 1))
            return probe.getsockname()[0]
    except OSError:
        return "YOUR-PC-IP"


def open_when_ready(port: int) -> None:
    url = f"http://localhost:{port}"
    deadline = time.time() + START_TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/config", timeout=1).close()
        except OSError:
            time.sleep(0.5)
            continue
        webbrowser.open(url)
        return
    print("The server did not answer in time. Check the messages above.")


def main() -> None:
    from dotenv import load_dotenv

    exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    if getattr(sys, "frozen", False):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(exe_dir / "browsers"))
    load_dotenv(exe_dir / ".env")

    port = free_port(int(os.getenv("PRIVACYLENS_PORT", DEFAULT_PORT)))
    os.environ["PRIVACYLENS_PORT"] = str(port)
    if not os.getenv("GEMINI_API_KEY"):
        print("No GEMINI_API_KEY found: using the offline mock AI. Put a .env file next to PrivacyLens.exe to use Gemini.")

    print("PrivacyLens is starting.")
    print(f"Open on this PC:  http://localhost:{port}")
    print(f"Open on a phone (same Wi-Fi):  http://{lan_address()}:{port}")
    print("To stop, press Ctrl+C or close this window.")

    import uvicorn

    from app.server import app

    threading.Thread(target=open_when_ready, args=(port,), daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if getattr(sys, "frozen", False) and len(sys.argv) > 1 and (sys.argv[1] == "-c" or sys.argv[1].endswith(".py")):
        run_as_python()
    else:
        main()
