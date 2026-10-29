# Demo script

## Setup on Windows

1. Follow README section 2 (create `.venv`, install requirements and Playwright browsers, copy `.env.example` to `.env`, run `python -m app.server`). `run.bat` does the same, but its activate line is broken in the current version; check it before the demo.
2. Open http://localhost:8000 on the PC.
3. Phone: join the same Wi-Fi and open `http://<pc-ip>:8000`. Find the IP with `ipconfig` (IPv4 Address). Allow Python through Windows Firewall if asked.
4. For Gemini, put `GEMINI_API_KEY=...` in `.env`, run `python scripts/check_gemini.py`, and restart. Without a key the app uses the Mock.

The phone can watch and approve. Starting tasks, the leak test, settings, the raw view and the AI switch only work on the PC.

## Recorded video, 2 to 3 minutes

| Time | Screen | Say |
|---|---|---|
| 0:00 to 0:15 | Home page, empty frame | "AI browser agents send the whole page to the cloud. PrivacyLens decides what is sensitive on this machine and sends only a sanitized view." |
| 0:15 to 0:40 | Click the "Pay for my cart" chip, then Go. The checkout page appears. | "Here is a checkout page with a saved card, address and phone. The agent is running now." |
| 0:40 to 1:00 | Turn on "See what the AI sees". Black boxes cover the sensitive parts. Turn it off and on once. | "This is the view we produce for the AI. Card, address and contact details are blacked out." |
| 1:00 to 1:15 | Click the status button to show "Kept on this device". | "This list shows what was hidden and stays local." |
| 1:15 to 1:40 | Approval sheet appears: "Use your saved card number..." or "Pay ... with your card ending ...". Show it on the phone too, approve on the phone. | "The AI only knows a token for the card. Our code types the real number locally, and only after you approve." |
| 1:40 to 2:00 | Open "How it works". Show raw snapshot next to outbound text. | "Left is what the page said. Right is the exact text sent to the model. No card number, only tokens." |
| 2:00 to 2:15 | In "Leak test", click "Run leak test". Result shows it was blocked. | "This sends a canary straight to the guard, skipping the sanitizer. The guard blocks it." |
| 2:15 to 2:40 | In "AI choice" pick "Offline test AI that obeys the page". Back. Click the "Leave feedback" chip, Go. Open "How it works" and show the rejected actions in "Validation and approval decisions". | "This page hides instructions to paste the card into the feedback box. This test AI obeys them on purpose, and the validator rejects the card token because the box is not a card field." |
| 2:40 to 2:55 | Evaluation card in "How it works". | "On our scenarios: 29 values exposed without PrivacyLens, 0 with." |

Notes for recording:
- For the injection segment, select "Offline test AI that obeys the page" first; the normal Mock fills the feedback box with harmless text and shows no rejection. Switch back to Mock or Gemini afterwards. Check before recording that the rejections appear.
- Read the 29 and 0 from `detection.baseline.secrets_exposed_without_privacylens` and `detection.baseline.secrets_exposed_with` on the day of recording.

## Live demo with exact clicks

1. On the PC, open http://localhost:8000. On the phone, open `http://<pc-ip>:8000`.
2. Click "Pay for my cart", then "Go".
3. Toggle "See what the AI sees" on, then off.
4. Click the status button under the frame. Show "Kept on this device". Click "Close".
5. When "Needs your OK" appears, tap "Approve" on the phone. Repeat for each approval until the narration says "Done."
6. Click "How it works". Scroll to "What the page said vs. what the AI received".
7. Scroll to "Leak test" and click "Run leak test".
8. Scroll to "Evaluation" and read the baseline line.
9. In "AI choice", pick "Offline test AI that obeys the page". Click "Back". Click "Leave feedback", then "Go". Open "How it works" and show the rejected steps in the decisions list. Switch the AI choice back afterwards.
10. If asked about cancelling, start "Pay for my cart" again and press "Cancel" on the approval. The narration shows "Stopped: stopped by you."

## Offline fallback

- With no internet, keep the AI on Mock (default without a key, or switch it under "AI choice"). Every scenario runs offline; pages are served from this PC and external requests are blocked anyway.
- If Gemini is selected and the network drops, the run stops with "the AI could not be reached". Switch to Mock under "AI choice" and start again.
- If the phone cannot connect (guest Wi-Fi, firewall), approve on the PC. Same sheet, same result.
- If the server will not start, play the recorded video and show eval/results.md.

## Things not to claim during the demo

- The model does not receive the screenshot. The blacked-out image is for the user.
- Gemini is not 100%: 94.4% task success over 3 runs per scenario (`gemini.task_success_pct`).
- Firefox was not tested; it would not launch on our machine. Chromium and WebKit were.
- Ollama is not implemented.
- The server has no login. Anyone on the Wi-Fi can watch the blacked-out view and approve steps. The raw page is limited to the PC.
