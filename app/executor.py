from urllib.parse import urlparse

from app.models import Action, Snapshot
from app.vault import TOKEN, Vault

LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}
LOCAL_SCHEMES = {"data", "blob", "about"}


async def block_external(context, on_block) -> None:
    """Abort every request that is not to this machine. Only the host name is logged, never the full URL."""
    async def handler(route):
        parsed = urlparse(route.request.url)
        if parsed.scheme in LOCAL_SCHEMES or parsed.hostname in LOCAL_HOSTS:
            await route.continue_()
        else:
            on_block(parsed.hostname or parsed.scheme)
            await route.abort()

    async def socket_handler(ws):
        if urlparse(ws.url).hostname not in LOCAL_HOSTS:
            on_block(urlparse(ws.url).hostname or "websocket")
            await ws.close()
        else:
            ws.connect_to_server()

    await context.route("**/*", handler)
    await context.route_web_socket("**/*", socket_handler)


def fill_value(value: str, vault: Vault) -> str:
    """The only place real secrets are put back, right before typing."""
    return TOKEN.sub(lambda m: vault.resolve(m.group(1)) or "", value)


async def execute(page, action: Action, raw: Snapshot, vault: Vault) -> None:
    if action.action == "wait":
        await page.wait_for_timeout(500)
        return
    if action.action == "scroll":
        await page.mouse.wheel(0, 600)
        return
    selector = next(e.selector for e in raw.elements if e.id == action.target)
    if action.action == "click":
        await page.click(selector, timeout=5000)
    elif action.action == "type":
        await page.fill(selector, fill_value(action.value, vault), timeout=5000)
    elif action.action == "select":
        await page.select_option(selector, label=fill_value(action.value, vault), timeout=5000)
