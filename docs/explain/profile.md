# profile.py

## What it does
Loads the user's saved details and the test canaries into the session vault at the start of every session.

## How
- `load_profile_into_vault` reads `config/user_profile.fake.json` and adds card number, CVV, expiry, name on card, address, phone, email and password to the vault. Each gets a token, so the AI can say "use `{{CARD#1}}`" without seeing the card.
- `load_canaries_into_vault` reads `scenarios/annotations.json` and adds every scenario's canary strings to `vault.canaries`.

## Likely judge questions
1. Is this real personal data? No. The file is fake, as the name says.
2. Why load the profile before the page is seen? So the AI has tokens to fill forms, and so the detectors and guard know these exact values even if they show up on a page in a form no regex catches.
3. What is a canary? A unique planted string on the test pages. If it ever appears in an outbound payload, something leaked. The guard blocks it by exact or compact match.
4. Is the profile file encrypted? No. It is a plain JSON file of fake data. A real product would need protected storage.
