import re

from app.detectors import find_sensitive
from app.models import Element, Snapshot
from app.rules import Rules
from app.structure import structural_type
from app.vault import Vault

COLLECT_JS = """
() => {
  const sx = window.scrollX, sy = window.scrollY;
  const buttonTypes = ['button', 'submit', 'reset', 'checkbox', 'radio', 'image'];
  const parents = new Map();
  const parentId = (p) => {
    if (!parents.has(p)) parents.set(p, { id: 'p' + parents.size, text: (p.textContent || '').slice(0, 20000) });
    return parents.get(p).id;
  };
  const pseudo = (el) => ['::before', '::after'].map(p => getComputedStyle(el, p).content)
    .map(c => /^".*"$/.test(c) ? c.slice(1, -1) : '').join(' ').trim();
  const out = [];
  let n = 0;
  for (const el of document.body.querySelectorAll('*')) {
    if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'HEAD'].includes(el.tagName)) continue;
    const tag = el.tagName.toLowerCase();
    const field = ['input', 'textarea', 'select'].includes(tag);
    const clickable = ['a', 'button', 'summary'].includes(tag) || el.hasAttribute('onclick')
      || el.getAttribute('role') === 'button' || (tag === 'input' && buttonTypes.includes(el.type));
    const ownNodes = [...el.childNodes].filter(c => c.nodeType === 3).map(c => c.textContent).join(' ').trim();
    const shown = clickable ? (el.innerText || (tag === 'input' ? el.value : '') || '').slice(0, 500) : ownNodes;
    const own = [shown, pseudo(el)].join(' ').trim();
    if (!own && !field && !clickable && !['video', 'img', 'iframe', 'canvas'].includes(tag)) continue;
    const id = 'e' + (++n);
    el.setAttribute('data-pl', id);
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    const lab = el.labels && el.labels[0] ? el.labels[0].textContent.trim() : '';
    const attrs = {};
    for (const a of ['type', 'autocomplete', 'name', 'id', 'aria-label', 'placeholder', 'title', 'alt'])
      if (el.getAttribute(a)) attrs[a] = el.getAttribute(a);
    attrs.label = lab;
    out.push({
      id, tag, attrs, own, field, cls: String(el.className || ''),
      inTile: el.closest('.tile, [class*=participant]') !== null,
      role: el.getAttribute('role') || '',
      value: field ? (el.type === 'checkbox' || el.type === 'radio' ? '' : el.value || '') : '',
      box: [r.left + sx, r.top + sy, r.width, r.height],
      hidden: cs.display === 'none' || cs.visibility === 'hidden' || el.closest('[aria-hidden=true]') !== null
        || !el.checkVisibility({ opacityProperty: true, visibilityProperty: true })
        || r.width < 2 || r.height < 2 || r.right < 0 || r.left < -1000 || r.left > innerWidth + 2000,
      href: tag === 'a' ? el.href : '',
      canClick: clickable,
      canType: field && !buttonTypes.includes(el.type) && el.tagName !== 'SELECT',
      isSubmit: ['button', 'input'].includes(tag) && ['submit', 'image'].includes(el.type),
      parent: el.parentElement ? parentId(el.parentElement) : '',
    });
  }
  const clone = document.body.cloneNode(true);
  clone.querySelectorAll('script,style,noscript').forEach(e => e.remove());
  const attrText = [...document.body.querySelectorAll('*')].flatMap(e =>
    [...e.attributes].filter(a => /^(title|alt|data-(?!pl$).*)$/.test(a.name)).map(a => a.value));
  const tidy = (t) => t.replace(/[ \\t]+/g, ' ').replace(/\\n\\s*\\n+/g, '\\n');
  return {
    elements: out, text: tidy(clone.textContent), visible: tidy(document.body.innerText), attrText,
    parents: Object.fromEntries([...parents.values()].map(p => [p.id, p.text])),
  };
}
"""

TEXT_NODES_JS = """
() => {
  window.__plNodes = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const texts = [];
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const p = node.parentElement;
    if (!p || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(p.tagName) || !node.textContent.trim()) continue;
    window.__plNodes.push(node);
    texts.push(node.textContent);
  }
  return texts;
}
"""

RANGE_BOXES_JS = """
(spans) => {
  const sx = window.scrollX, sy = window.scrollY;
  return spans.flatMap(([i, start, end]) => {
    const range = document.createRange();
    range.setStart(window.__plNodes[i], start);
    range.setEnd(window.__plNodes[i], end);
    return [...range.getClientRects()].map(r => [r.left + sx, r.top + sy, r.width, r.height]);
  });
}
"""


PARTICIPANT_NAME = re.compile(r"\b(nm|name|participant\w*)\b", re.I)
# Detection is linear, but a hostile page can still be huge; nothing past this is read.
MAX_TEXT = 200_000


def _structure_of(raw: dict) -> tuple[str, str] | None:
    if raw["field"]:
        return structural_type(raw["attrs"])
    if raw["inTile"] and raw["own"] and not raw["canClick"] and PARTICIPANT_NAME.search(raw["cls"]):
        return "NAME", "participant name in a call tile"
    return None


def _to_element(raw: dict) -> Element:
    attrs = raw["attrs"]
    found = _structure_of(raw)
    label = attrs.get("aria-label") or attrs.get("label") or attrs.get("placeholder") or attrs.get("title") \
        or attrs.get("alt") or attrs.get("name", "")
    return Element(
        id=raw["id"], tag=raw["tag"], role=raw["role"], label=label[:MAX_TEXT], text=raw["own"][:MAX_TEXT],
        value=raw["value"][:MAX_TEXT],
        input_type=attrs.get("autocomplete") or attrs.get("type", ""), box=tuple(raw["box"]),
        selector=f'[data-pl="{raw["id"]}"]', sensitive_type=found[0] if found else "",
        sensitive_reason=found[1] if found else "", href=raw["href"], can_click=raw["canClick"], can_type=raw["canType"],
        hidden=raw["hidden"], is_submit=raw["isSubmit"], parent=raw["parent"],
    )


async def _text_range_boxes(page, rules: Rules, vault: Vault) -> list[tuple[str, tuple[float, float, float, float]]]:
    texts = await page.evaluate(TEXT_NODES_JS)
    spans, types = [], []
    for i, text in enumerate(texts):
        for f in find_sensitive(text, rules, vault):
            spans.append([i, f.start, f.end])
            types.append(f.type)
    if not spans:
        return []
    boxes = []
    for span, type_ in zip(spans, types):
        for box in await page.evaluate(RANGE_BOXES_JS, [span]):
            boxes.append((type_, tuple(box)))
    return boxes


async def take_snapshot(page, rules: Rules, vault: Vault) -> Snapshot:
    """Everything the agent can see on the page. Raw and local only until sanitized."""
    data = await page.evaluate(COLLECT_JS)
    attr_text = "\n".join(data["attrText"])
    return Snapshot(
        url=page.url[:MAX_TEXT],
        elements=[_to_element(raw) for raw in data["elements"]],
        page_text=(data["text"] + "\n" + attr_text)[:MAX_TEXT],
        visible_text=(data["visible"] + "\n" + attr_text)[:MAX_TEXT],
        parent_texts=data["parents"],
        aria=await page.locator("body").aria_snapshot(),
        screenshot=await page.screenshot(full_page=True),
        text_boxes=await _text_range_boxes(page, rules, vault),
    )
