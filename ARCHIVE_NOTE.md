# CloakBrowser — Archived (2026-07-10)

This folder contains the **CloakBrowser** experiment, archived for reference.
After ~6 months of work, the project was superseded by **FlowBoard** which uses
a Chrome extension + agent architecture to bypass Flow's bot detection more
reliably than Playwright-based browser automation.

## Why archived (not active)

- Playwright-based browser automation gets detected by Google Flow's bot filters.
- DOM selectors break weekly — LLM hallucination on Material icons.
- No persistent session — each run re-logs-in.
- Single-shot — no batch queue, no character consistency.

## What FlowBoard does differently

- Uses user's actual Chrome profile (Profile 6) with logged-in session.
- Extension captures Bearer token from real Flow API calls.
- Token-based proxy through user's existing cookies — Google sees it as
  normal user activity.
- Has batch workflows, character nodes, persistent boards.

## Status of the integration

- **FlowBoard** is the production path. See `../../flowboard/`.
- **CloakBrowser** code preserved here for reference / lessons learned.
- **`llm_agent.py`** uses Groq LLM for prompt synthesis — only valuable part.
- **`.env` removed** from this archive — original file at `../CloakBrowser/.env`.

## Files worth keeping for reference

- `groq_client.py` — Groq API wrapper, pattern reusable
- `prompt_templates.py` — system prompts for browser automation reasoning
- `env_loader.py` — robust .env loader (handles commented keys)
- `flow_explorer.py` — DOM dump utility

## Files deprecated

- `google_flow_bot.py` — Playwright clicker, brittle
- `cloakbrowser/` — CloakHQ's library, replaced by Flowboard extension
- `login_bot.py` — Google login automation, replaced by Chrome session

## Last verified

- Date: 2026-07-10
- Working alternative: `../../flowboard/` (Flowboard Agent + Chrome extension)
- Live test: 6.27 MB MP4 downloaded from Flow via Flowboard API in ~90s.