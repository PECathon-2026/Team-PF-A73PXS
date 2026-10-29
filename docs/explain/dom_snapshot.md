# dom_snapshot.py

## What it does
Captures what the agent can see on the page: elements, full page text, the accessibility tree, a full-page screenshot, and the screen boxes of sensitive text. The result is a raw `Snapshot`. It stays local until the sanitizer runs.

## How
- `COLLECT_JS` runs in the page. It walks every element and keeps those with their own text, form fields, clickable things, videos and images. It tags each with `data-pl="eN"` and records attributes, value, box, hidden state and whether it sits in a call tile. It marks an element hidden when it is `display:none`, `visibility:hidden`, under `aria-hidden`, fails `checkVisibility`, is smaller than 2 px or sits far off-screen. It returns the full body text (hidden text included, kept local), the visible text (`innerText`), `title`, `alt` and `data-*` attribute values, and the text of each element's parent (`parent_texts`) so values split over sibling tags can be found.
- `_to_element` builds an `Element`. `_structure_of` uses `structural_type` for fields, and marks NAME for non-clickable text inside a `.tile` or participant container whose class contains "name", "nm" or "participant".
- `_text_range_boxes` collects every text node (`TEXT_NODES_JS`), runs `find_sensitive` on each, and asks the browser for the pixel rectangles of each match (`RANGE_BOXES_JS`). These are blacked out on the screenshot later.
- `take_snapshot` puts it together. Each selector is `[data-pl="eN"]` so the executor can find the element again.

## Likely judge questions
1. Is hidden text sent to the AI? No. The sanitizer builds `page_text` from the visible text plus attribute text, and hidden elements are left out of the element list. The full text with hidden parts stays local (the raw view in How it works).
2. How are participant names in a video call found? Only by the tile rule in `_structure_of`. A name outside such a container, without "my name is" and not saved in the vault, is not found.
3. Why scan per text node for boxes? A range on one text node gives exact rectangles. A value split across elements (for example `<b>4111</b><b>1111</b>...`) is not matched per node; the sanitizer finds it in `parent_texts`, hides every fragment, and blacks out each changed element's box.
4. Does the screenshot go to the AI? No. The prompt is text only. The blacked-out screenshot is shown in the UI as the AI view.
