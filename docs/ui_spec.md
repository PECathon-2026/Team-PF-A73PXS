# UI spec

**Feel:** like an Apple product. An everyday person never has to think: PrivacyLens quietly makes the AI safer. Show outcomes, hide the machinery, reveal details only when asked.

## Rules
- One primary action per screen, nothing technical on the main screen.
- Human words: "Hidden", "Kept on this device", "Nothing private was shared", "Needs your OK". Never "REDACTED", "guard", "payload", "LLM" or "token" outside the "How it works" view.
- System font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`), one accent color, generous spacing, rounded corners, soft shadows.
- Motion 200 to 300 ms with ease, respects `prefers-reduced-motion`.
- Light and dark follow `prefers-color-scheme` through CSS custom properties. No theme switch.
- Mobile-first, 375 px to 1440 px, touch targets at least 44 px. Phones: one column, controls in the thumb zone, approvals in a bottom sheet. Laptops: same elements, centered.
- Real buttons, inputs and labels, visible focus rings, 4.5:1 contrast in both themes, `aria-live` for status changes.

## Main screen
1. Task box "What should I do?" with one **Go** button. Below it, one suggestion chip per scenario; a chip fills in the task and picks the scenario.
2. Live view of the page (latest screenshot). Hidden items show a soft frosted overlay with a small "Hidden" tag, drawn locally only.
3. One switch, **See what the AI sees**, crossfades to the blacked-out screenshot and shows the placeholders.
4. One status line: "4 things hidden · nothing private shared". When blocked: "Stopped 1 unsafe message".
5. One-line narration of the current step.

## Approval sheet
Bottom sheet on phones, centered on laptops. One sentence ("Pay Rs 1,499 with your card ending 1111?"), a large **Approve**, a quiet **Cancel**, a "Why am I asked?" link. Routine steps never interrupt.

## Status details
Tap the status line for the list of hidden items, each with its human reason, plus anything blocked and why.

## How it works view
Small link at the bottom. Pipeline steps, raw snapshot next to the outbound payload, validation and approval decisions, eval results, privacy settings (per-type toggles, "Always hide..." rule), AI choice (Gemini, Mock), and a **Run leak test** button that sends a planted canary past the sanitizer to show the guard blocking it.

## Phone as approval remote
Opening the same URL on a phone joins the current session. Approvals show on both devices; the first answer wins.
