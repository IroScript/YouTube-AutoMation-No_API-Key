import os
import sys
import time
from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USERSCRIPT_PATH = os.path.join(SCRIPT_DIR, "ai_chat_auto_saver.user.js")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def test_tampermonkey_script(url="https://chatgpt.com", prompt="Write 1 short sentence about galaxies"):
    print(f"[Tampermonkey Test] Reading script from: {USERSCRIPT_PATH}")
    with open(USERSCRIPT_PATH, "r", encoding="utf-8") as f:
        js_code = f.read()

    with sync_playwright() as p:
        print("[Tampermonkey Test] Launching Chromium browser...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"[Tampermonkey Test] Navigating to {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        print("[Tampermonkey Test] Injecting Tampermonkey Userscript into page...")
        page.evaluate(js_code)
        time.sleep(2)

        # Verify floating panel is created
        print("[Tampermonkey Test] Verifying #ai-auto-panel existence...")
        panel = page.locator("#ai-auto-panel")
        if panel.count() == 0:
            print("[Tampermonkey Test] ERROR: #ai-auto-panel floating panel was not created!")
            sys.exit(1)
        print("[Tampermonkey Test] SUCCESS: Floating Control Panel (#ai-auto-panel) is rendered!")

        # Type prompt into panel textarea
        print(f"[Tampermonkey Test] Typing prompt into widget: '{prompt}'...")
        page.fill("#ai-prompt-input", prompt)
        time.sleep(1)

        # Click Run button on floating widget
        print("[Tampermonkey Test] Clicking Run button on Tampermonkey panel...")
        page.click("#ai-btn-run")

        # Monitor status
        print("[Tampermonkey Test] Monitoring automation execution status...")
        for _ in range(30):
            time.sleep(2)
            status = page.inner_text("#status-text")
            print(f"[Tampermonkey Test] Panel Status: {status}")
            if "Finished" in status or "Copied" in status or "Saved" in status:
                print("[Tampermonkey Test] Automation completed successfully via Tampermonkey panel!")
                break

        print("[Tampermonkey Test] Test finished!")
        browser.close()

if __name__ == "__main__":
    test_tampermonkey_script()
