# YouTube Automation + Flowboard

> **Note (2026-07-11):** CloakBrowser wrapper removed from this repo. Scripts now rely on **Chrome extension** (Flowboard Bridge) for browser-side automation and cookie capture.

This repo combines two related projects:

1. **Flowboard** (`flowboard/`) — local-only AI media workflow canvas powered by Google Flow (Pro plan). Lets you generate images/videos on a node-based board, with auto-prompt via local LLMs (Claude Code / Codex / Gemini CLI).
2. **YouTube Automation** (root `.py` files) — automation scripts for YouTube tasks (login, flow explorer, LLM agent, etc.) using Google Flow as backend.

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
├── google_flow_bot.py          # YouTube automation: Google Flow integration
├── login_bot.py                # YouTube automation: login flows
├── llm_agent.py                # LLM agent coordinator
├── cohere_client.py            # Cohere API wrapper
├── groq_client.py              # Groq API wrapper
├── flow_explorer.py            # Google Flow API explorer
├── web_tools.py                # Web utility functions
├── prompt_templates.py         # Prompt template library
├── env_loader.py               # .env loader
├── diagnose_report.py          # Diagnostic reporting
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

These scripts interact with Google Flow and YouTube via browser automation. Run individually:

```bash
python google_flow_bot.py    # Generate content via Google Flow
python login_bot.py          # Login automation
python flow_explorer.py      # Explore Flow projects
python llm_agent.py          # LLM-driven automation
```

Each script uses environment variables from `.env` (copy `.env.example`).

---

## 📝 License

MIT — see [LICENSE](LICENSE).