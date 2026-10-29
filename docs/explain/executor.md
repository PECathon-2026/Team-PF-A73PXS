# executor.py

## What it does
Carries out an approved action in the real browser, and blocks every browser request that is not to this machine.

## How
- `block_external(context, on_block)` installs a Playwright route for HTTP requests and one for WebSockets on the whole browser context. Requests to `localhost`, `127.0.0.1` or `::1`, or with a `data`, `blob` or `about` scheme, continue. Everything else is aborted or closed, and only the last two labels of the host (`site_of`) are reported, because the rest of a host name can carry data.
- It also adds an init script (`NO_WEBRTC_JS`) that removes `RTCPeerConnection` and the other WebRTC constructors from every page and frame, because WebRTC traffic does not pass through Playwright routes. server.py also starts Chromium with proxy-only WebRTC as a second lock.
- `fill_value(value, vault)` replaces each `{{TYPE#n}}` token with the real value from the vault. This is the only place real secrets are put back, right before typing.
- `execute(page, action, raw, vault)` handles wait (500 ms), scroll (600 px), click, type (`page.fill`) and select (`page.select_option` by label). It looks up the element's selector in the raw snapshot.

## Likely judge questions
1. Where does the real card number appear? Only inside the local browser, through `fill_value` in `execute`. It never passes through the AI.
2. Could a page send data to an attacker server? Not through HTTP requests or WebSockets; `block_external` aborts them, and WebRTC is removed. Blocked sites appear in the audit log. Channels outside the browser context are not covered.
3. Why log only the site? The full URL, and even the full host name, could carry leaked data, so only the last two host labels are logged.
4. What if the target id is missing? The validator already rejects unknown ids. If it still is not found, `execute` raises `LookupError`, and agent.py blocks the step.
