# Playwright Web Chat Automation Guide

## Overview
This folder contains the Playwright implementation for automating web AI chat interfaces (ChatGPT, Claude, Gemini) using Google Chrome with **Profile 7**.

- **Chrome Executable**: `C:\Program Files\Google\Chrome\Application\chrome.exe`
- **Profile Path**: `C:\Users\Irak\AppData\Local\Google\Chrome\User Data\Profile 7`

## Files
- [`playwright_chat_test.py`](file:///C:/Users/Irak/Desktop/AntiBotBrowser/WebInterfaceChatForPrompts/playwright/playwright_chat_test.py): Main Python script using Playwright.
- `output.txt`: Generated AI response output file.
- `prompt.txt` (Optional): Default prompt input file.

## How to Run

### Method 1: CDP Connection (Recommended if Chrome is already open)
Launch Chrome with remote debugging enabled on port 9222:
```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --profile-directory="Profile 7"
```
Then run the Playwright test script:
```powershell
python playwright/playwright_chat_test.py --url "https://chatgpt.com" --prompt "Write a short poem about AI"
```

### Method 2: Direct Persistent Context Launch (When Chrome is closed)
```powershell
python playwright/playwright_chat_test.py --url "https://chatgpt.com" --prompt "Explain quantum computing in 2 lines"
```

## Features
- Automatically switches between CDP mode and persistent launch mode.
- Interacts with ChatGPT, Claude, and Gemini DOM elements.
- Detects response generation completion.
- Extracts clean markdown response and writes it to `output.txt`.
