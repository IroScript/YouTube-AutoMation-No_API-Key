# YouTube Automation + Flowboard

> **Note (2026-07-11):** CloakBrowser wrapper removed from this repo. Scripts now rely on **Chrome extension** (Flowboard Bridge) for browser-side automation and cookie capture.

This repo combines two related projects:

1. **Flowboard** (`flowboard/`) — local-only AI media workflow canvas powered by Google Flow (Pro plan). Lets you generate images/videos on a node-based board, with auto-prompt via local LLMs (Claude Code / Codex / Gemini CLI).
2. **YouTube Automation** — automation scripts (CloakBrowser-dependent ones now archived). Remaining scripts (`web_tools.py`, `prompt_templates.py`, `env_loader.py`, `diagnose_report.py`) are standalone utilities.

---

## 🚀 Quick Start — Flowboard

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
├── flowboard/                  # Flowboard project (local AI media workflow)
│   ├── agent/                  # FastAPI backend (Python)
│   ├── frontend/               # React + Vite UI
│   └── extension/              # Chrome extension (browser-side cookie capture)
│
├── web_tools.py                # Web utility functions (kept)
├── prompt_templates.py         # Prompt template library (kept)
├── env_loader.py               # .env loader (kept; minor cloak-related comment)
├── diagnose_report.py          # Diagnostic reporting (kept)

# Archived CloakBrowser-dependent scripts (2026-07-11):
# Local copy: ~/Desktop/CloakBrowser_Archive/cloak-browser-scripts/
# ├── google_flow_bot.py  (CloakBrowser API → archived)
# ├── login_bot.py        (CloakBrowser API → archived)
# ├── llm_agent.py        (CloakBrowser API → archived)
# ├── cohere_client.py    (CloakBrowser API → archived)
# ├── groq_client.py      (CloakBrowser API → archived)
# └── flow_explorer.py    (CloakBrowser API → archived)
│
├── start_flowboard.bat         # One-click launcher (Agent + Frontend)
├── stop_flowboard.bat          # One-click stopper
├── FLOWBOARD_GUIDE.md          # Detailed Flowboard setup guide
│
├── pyproject.toml              # Python project metadata
├── CHANGELOG.md                # Changelog
├── LICENSE                     # MIT License
└── .env.example                # Environment variables template
```

---

## 🔧 Requirements

- **Python 3.12** with stdlib (Windows: ensure `C:\Python312\python312.zip` exists)
- **Node.js 18+** with `npm`
- **Chrome / Chromium** browser
- **Google Flow Pro plan** (for image/video generation; Free tier rejects video)
- **Claude Code** CLI (for Flowboard's auto-prompt + vision)

---

## 🤖 YouTube Automation Scripts

The remaining scripts (`web_tools.py`, `prompt_templates.py`, `env_loader.py`, `diagnose_report.py`) are standalone — they don't depend on CloakBrowser.

### Archived CloakBrowser Scripts

The previous CloakBrowser-dependent scripts have been **archived** to:

```
~/Desktop/CloakBrowser_Archive/cloak-browser-scripts/
```

These scripts cannot run as-is after the CloakBrowser wrapper removal. To revive them, rewrite the browser automation layer using **Playwright** or **Selenium** directly (no stealth wrapper).

---

## 📝 License

MIT — see [LICENSE](LICENSE).