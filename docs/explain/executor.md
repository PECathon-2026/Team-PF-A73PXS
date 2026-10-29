# executor.py

## What it does
Carries out an approved action in the real browser, and blocks every browser request that is not to this machine.

## How
- `block_external(context, on_block)` installs a Playwright route on the whole browser context. Requests to `localhost`, `127.0.0.1` or `::1`, or with a `data`, `blob` or `about` scheme, continue. Everything else is aborted and only the host name is reported.
- `fill_value(value, vault)` replaces each `{{TYPE#n}}` token with the real value from the vault. This is the only place real secrets are put back, right before typing.
- `execute(page, action, raw, vault)` handles wait (500 ms), scroll (600 px), click, type (`page.fill`) and select (`page.select_option` by label). It looks up the element's selector in the raw snapshot.

## Likely judge questions
1. Where does the real card number appear? Only inside the local browser, through `fill_value` in `execute`. It never passes through the AI.
2. Could a page send data to an attacker server? Not through HTTP requests from the page; `block_external` aborts them. Blocked hosts appear in the audit log. The route covers requests Playwright routes, which does not include WebSocket traffic.
3. Why not block by full URL? Logging the full URL could leak query-string data, so only the host is logged.
4. What if the target id is missing? The validator already rejects unknown ids, so `execute` assumes it exists.
