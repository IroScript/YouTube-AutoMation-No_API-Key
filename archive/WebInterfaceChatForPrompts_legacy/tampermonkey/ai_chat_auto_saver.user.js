// ==UserScript==
// @name         AI Chat Automation & Auto-Saver (ChatGPT, Claude, Gemini)
// @namespace    http://tampermonkey.net/
// @version      1.1
// @description  Automates prompt injection, submission, response completion detection, auto-copying, and file saving for ChatGPT, Claude, and Gemini.
// @author       Irak
// @match        https://chatgpt.com/*
// @match        https://claude.ai/*
// @match        https://gemini.google.com/*
// @run-at       document-end
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_download
// @grant        GM_setClipboard
// ==/UserScript==

(function() {
    'use strict';

    function getPlatform() {
        const host = window.location.hostname;
        if (host.includes('chatgpt.com')) return 'chatgpt';
        if (host.includes('claude.ai')) return 'claude';
        if (host.includes('gemini.google.com')) return 'gemini';
        return 'unknown';
    }

    const platform = getPlatform();
    let siteSpan, promptInput, btnRun, btnCopy, btnSave, statusDot, statusText, chkAutoCopy, chkAutoSave;
    let lastExtractedText = "";

    // Modern floating UI CSS
    const style = document.createElement('style');
    style.innerHTML = `
        #ai-auto-panel {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 999999;
            width: 320px;
            background: #1e1e2e;
            color: #cdd6f4;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            padding: 16px;
            border: 1px solid #45475a;
            font-size: 13px;
        }
        #ai-auto-panel h4 {
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #89b4fa;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        #ai-auto-panel textarea {
            width: 100%;
            height: 60px;
            background: #313244;
            color: #f5e0dc;
            border: 1px solid #45475a;
            border-radius: 6px;
            padding: 8px;
            box-sizing: border-box;
            resize: vertical;
            margin-bottom: 10px;
            font-size: 12px;
        }
        #ai-auto-panel .btn-group {
            display: flex;
            gap: 6px;
            margin-bottom: 10px;
        }
        #ai-auto-panel button {
            flex: 1;
            padding: 8px 10px;
            background: #89b4fa;
            color: #11111b;
            border: none;
            border-radius: 6px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.2s;
        }
        #ai-auto-panel button:hover {
            background: #b4befe;
        }
        #ai-auto-panel button.secondary {
            background: #45475a;
            color: #cdd6f4;
        }
        #ai-auto-panel button.secondary:hover {
            background: #585b70;
        }
        #ai-auto-panel .status-bar {
            padding: 6px 10px;
            background: #313244;
            border-radius: 6px;
            font-size: 11px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        #ai-auto-panel .status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #a6e3a1;
            display: inline-block;
            margin-right: 6px;
        }
        #ai-auto-panel .status-indicator.busy {
            background: #f9e2af;
            animation: pulse 1s infinite alternate;
        }
        @keyframes pulse {
            from { opacity: 0.4; }
            to { opacity: 1; }
        }
        #ai-auto-panel label {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-top: 6px;
            cursor: pointer;
            font-size: 11px;
        }
    `;
    
    function mountPanel() {
        if (document.getElementById('ai-auto-panel')) return;
        if (!document.body || !document.head) {
            setTimeout(mountPanel, 100);
            return;
        }
        document.head.appendChild(style);

        // Create Panel Element
        const panel = document.createElement('div');
        panel.id = 'ai-auto-panel';
        panel.innerHTML = `
            <h4>🤖 AI Auto-Saver <span style="font-size:10px; color:#a6adc8;" id="panel-site">Detecting...</span></h4>
            <textarea id="ai-prompt-input" placeholder="Type prompt here and click Run..."></textarea>
            <div class="btn-group">
                <button id="ai-btn-run">🚀 Run</button>
                <button id="ai-btn-copy" class="secondary">📋 Copy</button>
                <button id="ai-btn-save" class="secondary">💾 Save</button>
            </div>
            <div class="status-bar">
                <span><span class="status-indicator" id="status-dot"></span><span id="status-text">Ready</span></span>
            </div>
            <label><input type="checkbox" id="chk-autocopy" checked> Auto-Copy to Clipboard</label>
            <label><input type="checkbox" id="chk-autosave" checked> Auto-Download TXT</label>
        `;
        document.body.appendChild(panel);
        initEvents();
    }

    if (document.readyState === 'loading') {
        window.addEventListener('DOMContentLoaded', mountPanel);
    } else {
        mountPanel();
    }
    function initEvents() {
        siteSpan = document.getElementById('panel-site');
        promptInput = document.getElementById('ai-prompt-input');
        btnRun = document.getElementById('ai-btn-run');
        btnCopy = document.getElementById('ai-btn-copy');
        btnSave = document.getElementById('ai-btn-save');
        statusDot = document.getElementById('status-dot');
        statusText = document.getElementById('status-text');
        chkAutoCopy = document.getElementById('chk-autocopy');
        chkAutoSave = document.getElementById('chk-autosave');

        btnRun.addEventListener('click', runAutomation);
        btnCopy.addEventListener('click', copyResponse);
        btnSave.addEventListener('click', saveResponse);

        if (siteSpan) siteSpan.innerText = platform.toUpperCase();
    }

    function setStatus(text, isBusy = false) {
        statusText.innerText = text;
        if (isBusy) {
            statusDot.classList.add('busy');
            statusDot.style.background = '#f9e2af';
        } else {
            statusDot.classList.remove('busy');
            statusDot.style.background = '#a6e3a1';
        }
    }

    // Input & Send Selectors
    function getSelectors() {
        if (platform === 'chatgpt') {
            return {
                input: '#prompt-textarea',
                sendBtn: 'button[data-testid="send-button"], button[aria-label="Send prompt"]',
                stopBtn: 'button[data-testid="stop-button"], button[aria-label="Stop streaming"]',
                responses: 'div.markdown, div[data-message-author-role="assistant"]'
            };
        } else if (platform === 'claude') {
            return {
                input: 'div[contenteditable="true"]',
                sendBtn: 'button[aria-label="Send Message"], button:has(svg)',
                stopBtn: 'button:has-text("Stop")',
                responses: 'div.font-claude-message'
            };
        } else if (platform === 'gemini') {
            return {
                input: 'rich-textarea div[contenteditable="true"], div[contenteditable="true"]',
                sendBtn: 'button.send-button, button[aria-label*="Send"]',
                stopBtn: 'button[aria-label*="Stop"]',
                responses: 'message-content, div.model-response-text'
            };
        }
        return {
            input: 'textarea, div[contenteditable="true"]',
            sendBtn: 'button[type="submit"]',
            stopBtn: 'button[aria-label*="Stop"]',
            responses: 'article, div.markdown'
        };
    }

    function injectText(elem, text) {
        elem.focus();
        if (elem.tagName === 'TEXTAREA' || elem.tagName === 'INPUT') {
            elem.value = text;
            elem.dispatchEvent(new Event('input', { bubbles: true }));
            elem.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            elem.innerText = text;
            elem.dispatchEvent(new InputEvent('input', { bubbles: true }));
        }
    }

    function findInputElem() {
        const sel = getSelectors();
        let elem = document.querySelector(sel.input);
        if (elem) return elem;
        // Fallback selectors across platforms
        return document.querySelector('#prompt-textarea') ||
               document.querySelector('rich-textarea p') ||
               document.querySelector('div[contenteditable="true"]') ||
               document.querySelector('textarea') ||
               document.querySelector('p.placeholder');
    }

    async function runAutomation() {
        try {
            const prompt = promptInput.value.trim();
            if (!prompt) {
                alert('Please enter a prompt first!');
                return;
            }

            const sel = getSelectors();
            setStatus('Searching for chat input box...', true);
            let inputElem = findInputElem();
            
            // Retry loop for up to 5 seconds if page is still rendering input area
            let retries = 0;
            while (!inputElem && retries < 10) {
                await new Promise(r => setTimeout(r, 500));
                inputElem = findInputElem();
                retries++;
            }

            if (!inputElem) {
                setStatus('Error: Input box not found!', false);
                return;
            }

            setStatus('Typing prompt...', true);
            injectText(inputElem, prompt);

            await new Promise(r => setTimeout(r, 500));

            const sendBtn = document.querySelector(sel.sendBtn);
            if (sendBtn && !sendBtn.disabled) {
                sendBtn.click();
                setStatus('Prompt submitted. Waiting for response...', true);
            } else {
                // Trigger Enter Key
                inputElem.dispatchEvent(new KeyboardEvent('keydown', {
                    key: 'Enter', keyCode: 13, code: 'Enter', bubbles: true
                }));
                setStatus('Submitted via Enter key...', true);
            }

            // Monitor stream completion
            await waitForCompletion(sel);
        } catch (err) {
            console.error('[AI Auto-Saver Error]', err);
            setStatus(`Error: ${err.message}`, false);
        }
    }

    function waitForCompletion(sel) {
        return new Promise((resolve) => {
            let checkCount = 0;
            const interval = setInterval(() => {
                checkCount++;
                const stopBtn = document.querySelector(sel.stopBtn);
                if (!stopBtn || checkCount > 60) {
                    clearInterval(interval);
                    extractAndProcessResponse(sel);
                    resolve();
                }
            }, 1000);
        });
    }

    function extractAndProcessResponse(sel) {
        const responseElems = document.querySelectorAll(sel.responses);
        if (responseElems.length > 0) {
            const lastResp = responseElems[responseElems.length - 1];
            lastExtractedText = lastResp.innerText.trim();

            setStatus('Response completed & extracted!', false);

            if (chkAutoCopy.checked) {
                copyResponse();
            }
            if (chkAutoSave.checked) {
                saveResponse();
            }
        } else {
            setStatus('Finished (No response text found)', false);
        }
    }

    function copyResponse() {
        if (!lastExtractedText) {
            alert('No response text to copy!');
            return;
        }
        if (typeof GM_setClipboard !== 'undefined') {
            GM_setClipboard(lastExtractedText);
        } else {
            navigator.clipboard.writeText(lastExtractedText);
        }
        setStatus('Copied to Clipboard! 📋', false);
    }

    function saveResponse() {
        if (!lastExtractedText) {
            alert('No response text to save!');
            return;
        }
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `AI_Response_${platform}_${timestamp}.txt`;

        const blob = new Blob([lastExtractedText], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        setStatus(`Saved to ${filename} 💾`, false);
    }

})();
