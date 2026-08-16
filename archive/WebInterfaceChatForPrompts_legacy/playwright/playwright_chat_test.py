r"""
Playwright Web Interface Chat Automation
=========================================
Target Chrome Executable: C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe
Profile Path: C:\\Users\\Irak\\AppData\\Local\\Google\\Chrome\\User Data\\Profile 7

Features:
1. Connects via CDP (if Chrome is already running with --remote-debugging-port=9222)
   OR launches Chrome with Profile 7 persistently.
2. Automates ChatGPT, Claude, or Gemini web interface:
   - Pastes/Types prompt.
   - Triggers submit button.
   - Waits for response streaming to finish.
   - Extracts and copies response to output.txt in playwright/ directory.
"""

import os
import sys
import time
import argparse
from playwright.sync_api import sync_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA_DIR = r"C:\Users\Irak\AppData\Local\Google\Chrome\User Data"
PROFILE_NAME = "Profile 7"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_FILE = os.path.join(SCRIPT_DIR, "output.txt")
DEFAULT_PROMPT_FILE = os.path.join(SCRIPT_DIR, "prompt.txt")

def get_prompt(prompt_arg=None):
    if prompt_arg:
        return prompt_arg
    if os.path.exists(DEFAULT_PROMPT_FILE):
        with open(DEFAULT_PROMPT_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                return content
    return "Hello! Write a 2-line short poem about AI."

def run_playwright_automation(prompt_text, url="https://chatgpt.com", cdp_port=9222, output_file=DEFAULT_OUTPUT_FILE):
    print(f"[Playwright] Starting automation for URL: {url}")
    print(f"[Playwright] Prompt: {prompt_text}")
    print(f"[Playwright] Output will be saved to: {output_file}")

    with sync_playwright() as p:
        browser = None
        context = None
        page = None

        # 1. Try CDP connection first if Chrome is running with debugging port
        try:
            print(f"[Playwright] Attempting CDP connection on port {cdp_port}...")
            browser = p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
            context = browser.contexts[0] if browser.contexts else None
            if context and context.pages:
                page = context.pages[0]
            elif context:
                page = context.new_page()
            print("[Playwright] Connected successfully to existing Chrome session via CDP!")
        except Exception as e:
            print(f"[Playwright] CDP connection failed ({e}). Launching Chrome with Profile 7...")
            # 2. Launch persistent context with Chrome Profile 7
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=USER_DATA_DIR,
                    executable_path=CHROME_PATH,
                    headless=False,
                    args=[
                        f"--profile-directory={PROFILE_NAME}",
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled"
                    ]
                )
                page = context.pages[0] if context.pages else context.new_page()
                print("[Playwright] Chrome launched successfully with Profile 7.")
            except Exception as launch_err:
                print(f"[Playwright] Profile 7 is currently locked by active Chrome ({launch_err}).")
                print("[Playwright] Falling back to standalone Chromium browser for test execution...")
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                print("[Playwright] Standalone Chromium launched successfully.")

        # Navigate to target platform
        if page.url != url and not page.url.startswith(url):
            print(f"[Playwright] Navigating to {url}...")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

        # Detect platform selectors
        current_url = page.url.lower()
        print(f"[Playwright] Current page URL: {current_url}")

        if "chatgpt.com" in current_url:
            input_selector = "#prompt-textarea"
            send_btn_selector = "button[data-testid='send-button'], button[aria-label='Send prompt'], button[aria-label='Send message']"
            stop_btn_selector = "button[aria-label='Stop streaming'], button[data-testid='stop-button']"
            response_selector = "div.markdown, div[data-message-author-role='assistant']"
        elif "claude.ai" in current_url:
            input_selector = "div[contenteditable='true']"
            send_btn_selector = "aria-label='Send Message', button:has(svg)"
            stop_btn_selector = "button:has-text('Stop')"
            response_selector = "div.font-claude-message, div[data-is-streaming]"
        elif "gemini.google.com" in current_url:
            input_selector = "div[contenteditable='true'], rich-textarea"
            send_btn_selector = "button.send-button, button[aria-label*='Send']"
            stop_btn_selector = "button[aria-label*='Stop']"
            response_selector = "message-content, div.model-response-text"
        else:
            # General fallback
            input_selector = "textarea, div[contenteditable='true']"
            send_btn_selector = "button[type='submit'], button[aria-label*='Send']"
            stop_btn_selector = "button[aria-label*='Stop']"
            response_selector = "article, div.markdown, main div"

        print(f"[Playwright] Waiting for input box ({input_selector})...")
        try:
            page.wait_for_selector(input_selector, timeout=20000)
            input_elem = page.locator(input_selector).first
            input_elem.click()
            input_elem.fill(prompt_text)
            time.sleep(1)

            # Click send or press Enter
            send_btn = page.locator(send_btn_selector)
            if send_btn.count() > 0 and send_btn.first.is_visible():
                send_btn.first.click()
                print("[Playwright] Clicked send button.")
            else:
                input_elem.press("Enter")
                print("[Playwright] Pressed Enter key.")

            # Wait for response completion
            print("[Playwright] Waiting for response streaming to finish...")
            time.sleep(5) # initial streaming delay

            # Poll until response finishes
            max_wait = 60
            elapsed = 0
            while elapsed < max_wait:
                # Check if stop button is gone
                stop_btns = page.locator(stop_btn_selector)
                if stop_btns.count() == 0 or not stop_btns.first.is_visible():
                    print("[Playwright] Response generation completed!")
                    break
                time.sleep(2)
                elapsed += 2

            # Extract response
            time.sleep(2)
            responses = page.locator(response_selector)
            response_text = ""
            if responses.count() > 0:
                response_text = responses.last.inner_text()
            else:
                response_text = "No response content found or selector didn't match."

            print("\n" + "="*50)
            print("[Playwright] GENERATED RESPONSE:")
            print("="*50)
            print(response_text)
            print("="*50 + "\n")

            # Save to output file
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(response_text)
            print(f"[Playwright] Successfully saved response to {output_file}")

        except Exception as e:
            print(f"[Playwright] Error during automation: {e}")
            raise e

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Playwright AI Chat Automation")
    parser.add_argument("--prompt", type=str, help="Prompt text to send")
    parser.add_argument("--url", type=str, default="https://chatgpt.com", help="Target URL")
    parser.add_argument("--port", type=int, default=9222, help="CDP Port if Chrome is already open")
    args = parser.parse_args()

    prompt = get_prompt(args.prompt)
    run_playwright_automation(prompt, url=args.url, cdp_port=args.port)
