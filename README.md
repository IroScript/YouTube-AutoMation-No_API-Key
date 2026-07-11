# Flowboard

> Local-only AI media workflow canvas. Node-based board for generating images/videos using **Google Flow (Pro plan)** with auto-prompt via local LLMs (Claude Code / Codex / Gemini CLI).

> **Note (2026-07-11):** CloakBrowser wrapper removed. Browser automation now done via the bundled **Chrome extension** (`flowboard/extension/`) which captures cookies/tokens from `labs.google/fx/tools/flow` and forwards them to the local agent.

> **Note (2026-07-11):** All non-essential content (CloakBrowser-era files + reference docs + session logs) moved to [`archive/`](archive/). This repo is now a single-purpose Flowboard project with a clean root.

---

## 🚀 Quick Start

### One-time setup

1. Install **Python 3.12** at `C:\Python312` (with stdlib + `python312.zip`)
2. Install **Node.js 18+**
3. **Chrome extension**: open `chrome://extensions/` → enable Developer mode → "Load unpacked" → select `flowboard/extension/`

### Run Flowboard

Double-click `start_flowboard.bat` (from repo root). It will:
- Start **Agent** (FastAPI on `:8101`) in its own Terminal window
- Start **Frontend** (Vite on `:5173`) in its own Terminal window
- Wait for both health-checks to pass

Then open: <http://localhost:5173/>

### Stop Flowboard

Double-click `stop_flowboard.bat`.

Full guide: see [`FLOWBOARD_GUIDE.md`](FLOWBOARD_GUIDE.md).

---

## 📁 Repo layout

```
.
├── flowboard/                  # Flowboard project (the active codebase)
│   ├── agent/                  # FastAPI backend (Python)
│   ├── frontend/               # React + Vite UI
│   └── extension/              # Chrome extension (browser-side cookie capture)
│
├── archive/                    # All non-active content (preserved)
│   ├── README.md               # What's in here and why
│   ├── .dockerignore, .env.example, .gitattributes
│   ├── CHANGELOG.md, LICENSE, pyproject.toml
│   ├── web_tools.py, prompt_templates.py, env_loader.py, diagnose_report.py
│   ├── Google Flow Steps.txt   # Reference notes (CloakBrowser era)
│   ├── Worked.txt              # Session notes
│   └── ❏ Puku CLI*.txt         # Puku CLI session logs
│
├── start_flowboard.bat         # One-click launcher (Agent + Frontend)
├── stop_flowboard.bat          # One-click stopper
├── FLOWBOARD_GUIDE.md          # Detailed Flowboard setup guide
└── README.md                   # This file
```

---

## 🔧 Requirements

- **Python 3.12** with stdlib (Windows: ensure `C:\Python312\python312.zip` exists)
- **Node.js 18+** with `npm`
- **Chrome / Chromium** browser
- **Google Flow Pro plan** (for image/video generation; Free tier rejects video)
- **Claude Code** CLI (for Flowboard's auto-prompt + vision)

---

## 📦 Archived content

All CloakBrowser-related history moved to [`archive/`](archive/). See [`archive/README.md`](archive/README.md) for contents.

If you need to revive archived automation scripts (e.g. `login_bot.py`, `google_flow_bot.py`):
- Rewrite the browser automation layer using **Playwright** or **Selenium** directly (no stealth wrapper)
- Tokens/cookies come from the Flowboard Chrome extension instead

Local backups of the deleted CloakBrowser-dependent scripts preserved at:
```
~/Desktop/CloakBrowser_Archive/cloak-browser-scripts/
```

---

## 📝 License

MIT — see [`archive/LICENSE`](archive/LICENSE) (moved with the rest of CloakBrowser-era repo state).