"""
Playwright ChatGPT YouTube Metadata Generator (Standalone)
==========================================================
Generates high-CTR Title, 3-Paragraph SEO Description, and Tags JSON for a video.
"""

import os
import re
import sys
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CHATGPT_URL = "https://chatgpt.com"


def fetch_youtube_metadata_via_playwright(video_title: str, topic: str = "", level_info: str = "Level 10 - ALIEN LEVEL / MAXIMUM") -> dict:
    """Generates standard structured YouTube metadata JSON."""
    prompt_text = f"""
Given the following AI-generated impossible giant machine video:
Video Subject: {video_title}
Topic/Element: {topic or 'General'}
Escalation Level: {level_info}

Please generate a professional YouTube metadata package in strict JSON format:
{{
  "title": "A high-CTR, curiosity-driven YouTube video title (under 80 chars, with 1 emoji)",
  "seo_description": "A 3-paragraph SEO-rich video description with timecodes, storyline breakdown, and 5 hashtags (#AI #Megastructure #Veo #SciFi #ImpossibleEngineering)",
  "tags": ["10-15 viral search tags as array of strings"],
  "category": "Science & Technology",
  "default_language": "en"
}}
Return ONLY the raw JSON object.
""".strip()

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            page.goto(CHATGPT_URL, wait_until="networkidle", timeout=60000)
            time.sleep(2)
            box = page.locator("#prompt-textarea").first
            box.click()
            box.fill(prompt_text)
            time.sleep(1)
            send_btn = page.locator('button[data-testid="send-button"]')
            if send_btn.count() > 0 and send_btn.first.is_visible():
                send_btn.first.click()
            else:
                box.press("Enter")

            time.sleep(10)
            elapsed = 0
            while elapsed < 60:
                stop_btn = page.locator('button[data-testid="stop-button"]')
                if stop_btn.count() == 0 or not stop_btn.first.is_visible():
                    break
                time.sleep(2)
                elapsed += 2

            responses = page.locator('div[data-message-author-role="assistant"], div.markdown')
            output_text = responses.last.inner_text() if responses.count() > 0 else ""
            browser.close()

            match = re.search(r'\{.*\}', output_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
    except Exception as e:
        print(f"[YouTube Metadata] Browser note ({e}). Generating high-quality standard SEO package.")

    # High-quality fallback
    return {
        "title": f"🚨 INSANE: {video_title} - Level 10 Impossible Megastructure 🌾",
        "seo_description": f"Witness the ultimate Level 10 Alien-Scale {video_title}! Operating at colossal scale across entire landscapes with automated harvesting arms and quantum telemetry.\n\n⏱️ TIMESTAMPS:\n0:00 - Step 1: Core Startup\n0:02 - Step 2: Mechanical Deployment\n0:04 - Step 3: Intake Acceleration\n0:06 - Step 4: Full Stabilization\n\n#ImpossibleMachine #AI #Veo #Megastructure #SciFiEngineering",
        "tags": [video_title, f"{topic} Machine", "Impossible Engineering", "AI Video", "Veo", "Megastructure", "Titan Harvester", "SciFi Concept", "Future Technology", "Colossal Machines"],
        "category": "Science & Technology",
        "default_language": "en"
    }
