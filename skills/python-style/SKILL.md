---
name: python-style
description: Python code style and tooling rules — Ruff linter on every modification, --break-system-packages flag for Homebrew Python on macOS, python-dotenv for env loading (never source .env). Use proactively when editing any .py file or installing Python packages.
triggers:
- edit python
- write python
- python script
- pip install
- ruff
- .py file
- python-dotenv
---

# python-style

Project-wide Python conventions. Auto-apply when touching any `.py` file.

## Linting

**Ruff is the linter.** Run after every modification to any Python file in any project.

```bash
ruff check <path>
ruff check --fix <path>   # auto-fix safe issues
ruff format <path>        # formatter
```

Don't claim a Python edit complete until Ruff passes on the changed file.

## Package installation (macOS Homebrew Python)

macOS Homebrew-managed Python rejects `pip install` without an explicit override. Use:

```bash
pip install --break-system-packages <package>
```

This is the team standard for macOS workstations. Do NOT recommend `pipx` or virtualenvs as a workaround unless the project explicitly uses them.

## Environment / secrets loading

- Load `.env` via `python-dotenv`. NEVER `source .env`.
- Tokens live in **per-project `.env` files**, not a single global one. The historical "all in `mb-mgmt/.env`" pointer is **stale** — that file no longer exists at the documented path. Refer to the `Credential Hygiene` section in CLAUDE.md for current canonical token locations (ClickUp PAT in `~/daily-briefing/.env`, Forge token embedded in `~/Sync/.git/config`, etc.).
- Never hardcode, never commit. See global Hard Rules in CLAUDE.md for the full secrets-handling policy.

```python
from dotenv import load_dotenv
load_dotenv()  # loads from the project's local .env
import os
api_key = os.environ["SOME_API_KEY"]
```

## Coding discipline (carries over from global CLAUDE.md)

- **Surface ambiguity before coding.** Multiple interpretations → present them, don't pick silently.
- **Goal-driven execution.** "fix the bug" → "write a test that reproduces it, then make it pass."
- **Clean up only YOUR orphans.** Remove imports/vars/functions your changes made unused. Don't touch pre-existing dead code unless asked.
