# Tampermonkey AI Chat Automation & Auto-Saver Guide

## Overview
This folder contains the Tampermonkey Userscript implementation. It runs directly inside Google Chrome (using **Profile 7**) whenever you open `chatgpt.com`, `claude.ai`, or `gemini.google.com`.

## Files
- [`ai_chat_auto_saver.user.js`](file:///C:/Users/Irak/Desktop/AntiBotBrowser/WebInterfaceChatForPrompts/tampermonkey/ai_chat_auto_saver.user.js): Tampermonkey Userscript file.

## How to Install in Chrome (Profile 7)

1. Open Chrome with Profile 7.
2. Install the **Tampermonkey** Extension from Chrome Web Store (if not already installed).
3. Click the Tampermonkey extension icon -> **Create a new script...**.
4. Copy all content from [`ai_chat_auto_saver.user.js`](file:///C:/Users/Irak/Desktop/AntiBotBrowser/WebInterfaceChatForPrompts/tampermonkey/ai_chat_auto_saver.user.js) and paste it into the editor.
5. Press `Ctrl + S` to Save.

## Features
- **In-Browser Control Panel**: Floating widget on bottom-right of chat pages.
- **Cross-Platform**: Supports ChatGPT, Claude, and Gemini.
- **Auto-Paste & Submit**: Paste prompt in widget, click **🚀 Run**, and it automatically submits to the AI chat interface.
- **Completion Detection**: Waits until AI finishes streaming the response.
- **Auto-Copy & Auto-Download**: Automatically copies the response to clipboard and downloads a `.txt` file with timestamp.
