# 🎨 Flowboard — কীভাবে চালাবে

তোমার PC-তে Flowboard একবার setup হয়ে গেছে (Python + venv + packages সব ঠিক)। এখন শুধু **৩টা server start করলেই** Flowboard চলবে।

---

## 📦 কী কী লাগবে

| জিনিস | ফাইল/ফোল্ডার | যেখানে আছে |
|---|---|---|
| Agent (Backend) | `flowboard/agent/` | `C:\Users\Irak\Desktop\AntiBotBrowser\flowboard\agent` |
| Frontend (UI) | `flowboard/frontend/` | `C:\Users\Irak\Desktop\AntiBotBrowser\flowboard\frontend` |
| Chrome Extension | `flowboard/extension/` | `C:\Users\Irak\Desktop\AntiBotBrowser\flowboard\extension` |

প্রতিবার Flowboard চালাতে **Agent** + **Frontend** চালু থাকতে হবে। **Extension** শুধু একবার Chrome-এ load করলেই হয়।

---

## 🚀 প্রথমবার Setup (একবারই)

### 1️⃣ Chrome Extension Load (একবারই)

1. Chrome browser ওপেন করো
2. Address bar-এ লেখো: `chrome://extensions/`
3. উপরে-ডানে **"Developer mode"** ON করো
4. **"Load unpacked"** বাটনে click করো
5. এই folder select করো:
   ```
   C:\Users\Irak\Desktop\AntiBotBrowser\flowboard\extension
   ```
6. ✅ Extension load হয়ে যাবে — Chrome-এ permanently থাকবে

---

## 🔄 প্রতিবার চালানোর Steps

তোমার দরকার ২টা Terminal window (Git Bash / PowerShell যেকোনোটা)।

### 🟦 Terminal 1 — Agent (Backend)

```bash
cd "C:\Users\Irak\Desktop\AntiBotBrowser\flowboard\agent"
.venv\Scripts\python.exe -m uvicorn flowboard.main:app --port 8101
```

সফল হলে দেখবে:
```
INFO:     flowboard agent started (ws:9223 + worker)
INFO:     Uvicorn running on http://127.0.0.1:8101
```

✅ এই window **বন্ধ করবে না** — agent চলতে থাকবে।

---

### 🟩 Terminal 2 — Frontend (UI)

```bash
cd "C:\Users\Irak\Desktop\AntiBotBrowser\flowboard\frontend"
npm run dev
```

সফল হলে দেখবে:
```
VITE v5.4.21  ready in 1000 ms
➜  Local:   http://localhost:5173/
```

✅ এটাও **বন্ধ করবে না** — UI server চলবে।

---

### 🌐 Browser Tab

Terminal 2-এ যে port দেখাচ্ছে (5173 / 5174 / 5175 — যেকোনোটা), সেটা browser-এ open করো:

```
http://localhost:5173/
```

---

## 🔑 Pro Plan Login (প্রথমবার একবার)

Flowboard UI তে:
1. **Settings** বা **Login** tab-এ যাও
2. Google Flow **Pro plan account** দিয়ে login (তোমার account)
3. Token save হয়ে যাবে — পরে আর চাইবে না

---

## 🎬 Image / Video Generate করা

1. UI তে prompt লেখো (যেমন: `a cat in space, cinematic`)
2. Model select করো:
   - 🖼️ **Image** → GEM_PIX_2 (Pro plan এ available)
   - 🎥 **Video** → Veo 3.1 (Pro plan এ available)
3. **Generate** click করো
4. Chrome extension automatically browser cookie/token নিয়ে agent-এ পাঠাবে
5. Google Flow API call হবে → result UI তে দেখাবে

---

## ⚡ সব চালু / বন্ধ করার সারাংশ

| কখন | কী করবে |
|---|---|
| **প্রথমবার** | Extension load করো + নিচের ২টা Terminal চালু করো |
| **প্রতিবার PC চালু করলে** | শুধু Terminal 1 + Terminal 2 চালু করো (Extension ও Browser tab আগের মতোই আছে) |
| **বন্ধ করতে চাইলে** | Terminal 1 ও 2 তে `Ctrl + C` চাপো |

---

## 🆘 Troubleshooting

| সমস্যা | সমাধান |
|---|---|
| `Connection refused` agent-এ | Terminal 1 চালু নেই — start করো |
| Frontend blank দেখাচ্ছে | Terminal 2 চালু নেই — start করো |
| "Extension not connected" | Chrome-এ extension enabled কিনা দেখো (`chrome://extensions/`) |
| Image/Video generate হচ্ছে না | Pro plan login আছে কিনা দেখো (UI settings এ) |

---

## 🔧 দরকারি Ports

| Service | Port | URL |
|---|---|---|
| Agent (REST API) | `8101` | http://127.0.0.1:8101/ |
| Agent Health | `8101` | http://127.0.0.1:8101/api/health |
| Agent WebSocket | `9223` | ws://127.0.0.1:9223 |
| Frontend (Vite) | `5173`/`5174`/`5175` | http://localhost:5173/ |

> 💡 Port `5173` অন্য কিছু দখল করলে Vite নিজেই `5174`, `5175` ব্যবহার করবে — Terminal output দেখে সঠিক port ব্যবহার করো।

---

## 🎁 Bonus: `start.bat` (Double-click এ চালু)

চাইলে double-click এ দুই server একসাথে চালু করতে পারো। নিচের content নিয়ে `start_flowboard.bat` নামে file বানাও `AntiBotBrowser` folder-এ:

```batch
@echo off
start "Flowboard Agent" cmd /k "cd /d C:\Users\Irak\Desktop\AntiBotBrowser\flowboard\agent && .venv\Scripts\python.exe -m uvicorn flowboard.main:app --port 8101"
timeout /t 3
start "Flowboard Frontend" cmd /k "cd /d C:\Users\Irak\Desktop\AntiBotBrowser\flowboard\frontend && npm run dev"
```

তারপর প্রতিবার শুধু `start_flowboard.bat` double-click করো — ২টা Terminal নিজে থেকেই খুলবে।

বন্ধ করতে: দুটো Terminal window-ই `Ctrl + C` চাপো, তারপর `exit` টাইপ করো।
