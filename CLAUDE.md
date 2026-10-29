# PrivacyLens (PECATHON'26, PS-004)

A privacy-preserving AI browser agent. Principle: compute what is sensitive locally, reason globally only on sanitized data.

## Goal
Cover every requirement of PS-004 and its bonus points. Judges read the code with us, so keep it simple and explainable. Requirements live in docs/requirements_matrix.md.

## Code style
- Idiomatic PEP 8 Python 3.11+, type hints on public functions, dataclasses for data shapes.
- Clear, specific names, consistent across files. Functions up to about 40 lines, files up to about 250.
- Plain functions over classes; classes only where state lives (LLM providers, session).
- Comment only the non-obvious why. No banner comments, no "Step 1" comments, no comments restating code.
- No emoji anywhere (code, logs, commits, docs, UI copy).
- No filler words in docs or UI: seamlessly, robust, leverage, comprehensive, cutting-edge, delve, elevate.
- No dead code, commented-out blocks, placeholder TODOs, factories, registries or base classes for one subclass.
- Handle errors where they can happen. The guard path fails closed.
- Imperative commit messages.

## Rules
- The Gemini key lives only in .env. Never print or log it. Logs, errors and outbound payloads carry placeholders only.
- Run scripts/precommit_scan.py before every commit.
- Ask the user before git push, publishing, deploying, system-wide installs, or network calls other than Gemini.
- Never claim something works unless a command run in this session proves it. STATUS.md keeps VERIFIED and NOT YET VERIFIED lists.
- Every metric in docs comes from eval/results.json. Leakage claims are scoped to the tested cases and pathways.
- Never skip, delete or xfail a failing test, and never loosen the guard to pass.
- Allowed dependencies: fastapi, uvicorn, playwright, httpx, python-dotenv, pytest, opencv-python, Pillow, psutil, numpy.
- Synthetic data only.
