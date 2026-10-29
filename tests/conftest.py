import functools
import http.server
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def base_url():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def pytest_collection_modifyitems(items):
    # Playwright's sync API (acceptance tests) keeps an event loop alive that breaks later asyncio.run calls.
    items.sort(key=lambda item: item.fspath.basename == "test_acceptance.py")
