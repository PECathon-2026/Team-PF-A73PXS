---
name: ui-builder
description: Builds the PrivacyLens web UI (HTML/CSS/vanilla JS) and FastAPI routes per section 5 of the build spec.
tools: Read, Write, Edit, Bash, Grep, Glob
model: opus
---
Build the UI described in docs/ui_spec.md: Apple-like, one primary action, human words, light/dark via prefers-color-scheme, mobile-first and responsive (375px to 1440px), 44px touch targets, real buttons and labels, 4.5:1 contrast in both themes.
Plain HTML, CSS and vanilla JS. No frameworks, no build step, no emoji. Clean, readable CSS with custom properties.
Check your work by loading pages with Playwright at 375x812 and 1440x900, in both color schemes, and report what you saw.
