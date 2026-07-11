# `archive/` — CloakBrowser Era (2026-07-10)

This folder preserves the repository's state **before the CloakBrowser wrapper was removed** (2026-07-11).

## Why archived?

The original `YouTube-AutoMation-No_API-Key` repo was built around **CloakBrowser** — a third-party stealth Chromium wrapper that required a binary download and proprietary license. On 2026-07-11 the project direction changed:

- CloakBrowser wrapper deleted
- Browser automation now handled by a **custom Chrome extension** (`flowboard/extension/`) that captures cookies/tokens directly from `labs.google/fx/tools/flow`
- CloakBrowser-dependent `.py` scripts (`login_bot.py`, `google_flow_bot.py`, etc.) deleted from repo root and preserved locally at `~/Desktop/CloakBrowser_Archive/cloak-browser-scripts/`

## What's in here

Files that were at repo root before the restructuring. Most are CloakBrowser-related config or generic Python utilities:

| File | Purpose |
|---|---|
| `.dockerignore` | Docker ignore rules (from CloakBrowser image builds) |
| `.env.example` | Example environment variables template |
| `.gitattributes` | Git line-ending rules |
| `CHANGELOG.md` | Project changelog (mostly CloakBrowser history) |
| `LICENSE` | MIT License |
| `pyproject.toml` | Python project metadata |
| `web_tools.py` | Generic web utility functions (no CloakBrowser dependency) |
| `prompt_templates.py` | Prompt template library (no CloakBrowser dependency) |
| `env_loader.py` | `.env` loader (has a minor cloak-related comment) |
| `diagnose_report.py` | Diagnostic reporting (no CloakBrowser dependency) |

## Reviving archived scripts

The Python scripts here are standalone — they don't import CloakBrowser. They can be used as-is if you have a working browser automation layer.

The deleted CloakBrowser-dependent scripts (now in `~/Desktop/CloakBrowser_Archive/cloak-browser-scripts/`) can be revived by rewriting the `cloakbrowser import launch` lines to use **Playwright** or **Selenium** directly. Token/cookie capture should come from the Flowboard Chrome extension via WebSocket.

---

**Date archived:** 2026-07-11
**Reason:** Repo restructured to single-purpose Flowboard project.