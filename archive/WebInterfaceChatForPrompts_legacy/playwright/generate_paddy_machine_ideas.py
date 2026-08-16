r"""
Playwright ChatGPT Idea Generator & SQLite/CSV Saver (JSON Structured Output)
=============================================================================
Fetches 10 Giant Impossible Paddy Machine Ideas from ChatGPT via Playwright
as a JSON array, saves each idea into a distinct database row in youtube_pipeline.db,
and exports ideas_separated.csv.
"""

import os
import re
import sys
import json
import time
import uuid
import csv
import sqlite3
BASE_DIR = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = str(BASE_DIR / "flowboard" / "agent")
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from flowboard.db.youtube_session import get_youtube_session, init_youtube_db
from flowboard.db.youtube_models import Idea, Category
from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "output.txt")
EXPORT_DIR = BASE_DIR / "flowboard" / "storage" / "exports"

PROMPT = """
Give me 10 creative impossible machine ideas related to paddy and rice harvesting.
Primary feature: Each machine MUST be giant in size (colossal megastructures, titan-scale).

CRITICAL FORMATTING INSTRUCTION:
Please return the 10 ideas strictly as a JSON array of 10 objects. Do not include any markdown conversational text before or after the JSON.

JSON Schema:
[
  {
    "id": 1,
    "title": "Machine Title",
    "description": "Short 2-3 sentence description of how the giant machine operates."
  }
]
"""

def fetch_response_via_playwright(prompt_text: str, url: str = "https://chatgpt.com", cdp_port: int = 9222) -> str:
    print("[Playwright] Starting browser automation...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print(f"[Playwright] Navigating to {url}...")
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(3)

        input_selector = "#prompt-textarea"
        print("[Playwright] Waiting for prompt input textarea...")
        page.wait_for_selector(input_selector, timeout=30000)
        
        input_elem = page.locator(input_selector).first
        input_elem.click()
        input_elem.fill(prompt_text)
        time.sleep(1)

        send_btn = page.locator('button[data-testid="send-button"]')
        if send_btn.count() > 0 and send_btn.first.is_visible():
            send_btn.first.click()
            print("[Playwright] Clicked send button.")
        else:
            input_elem.press("Enter")
            print("[Playwright] Pressed Enter.")

        print("[Playwright] Waiting for response streaming to finish...")
        time.sleep(10)

        max_wait = 90
        elapsed = 0
        while elapsed < max_wait:
            stop_btn = page.locator('button[data-testid="stop-button"], button[aria-label="Stop streaming"]')
            if stop_btn.count() == 0 or not stop_btn.first.is_visible():
                print("[Playwright] Response generation completed!")
                break
            time.sleep(3)
            elapsed += 3

        time.sleep(2)
        responses = page.locator('div[data-message-author-role="assistant"], div.markdown')
        response_text = responses.last.inner_text() if responses.count() > 0 else ""

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(response_text)

        browser.close()
        return response_text

def parse_json_ideas(response_text: str):
    """Parses JSON response into 10 separate idea dictionaries."""
    # Find json array block
    match = re.search(r'\[\s*\{.*\}\s*\]', response_text, re.DOTALL)
    if match:
        try:
            items = json.loads(match.group(0))
            if isinstance(items, list):
                return items
        except Exception as e:
            print(f"[JSON Parse Note]: Standard json parse failed ({e}). Fallback to regex.")

    # Fallback regex split
    ideas = []
    blocks = re.split(r'\n(?=\d+[\.\)]\s+)', response_text.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split('\n')
        header = lines[0].strip()
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else block
        
        title_match = re.search(r'^\d+[\.\)]\s*(?:\*\*)?([^\*\n]+)(?:\*\*)?', header)
        title = title_match.group(1).strip() if title_match else header
        
        ideas.append({
            "title": title[:200],
            "description": body
        })
    return ideas[:10]

def save_ideas_to_sqlite_and_csv(ideas_list):
    """Saves each idea into a distinct database row in youtube_pipeline.db and exports CSV."""
    init_youtube_db()
    
    with get_youtube_session() as session:
        cat = session.query(Category).filter(Category.name == "Impossible Giant Machine").first()
        cat_id = cat.id if cat else 1
        
        saved_records = []
        for idx, item in enumerate(ideas_list, 1):
            title = item.get("title", f"Paddy Machine Idea #{idx}")
            desc = item.get("description", "")
            
            new_idea = Idea(
                uuid=str(uuid.uuid4()),
                title=title,
                short_title=title,
                raw_idea=f"{title}\n{desc}",
                description=desc,
                category_id=cat_id,
                category="Impossible Giant Machine",
                topic="Paddy Harvesting",
                niche="Titan Megastructures",
                status="new",
                priority=idx
            )
            session.add(new_idea)
            saved_records.append(new_idea)
            
        session.commit()
        for r in saved_records:
            session.refresh(r)

    # Export to CSV
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    db_path = r"C:\Users\Irak\Desktop\AntiBotBrowser\flowboard\storage\youtube_pipeline.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, uuid, title, category, topic, description, created_at FROM ideas ORDER BY id ASC")
    rows = cur.fetchall()
    cols = ["id", "uuid", "title", "category", "topic", "description", "created_at"]

    csv_path = EXPORT_DIR / "ideas_separated.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)

    conn.close()
    return saved_records, csv_path

def run():
    print("=" * 60)
    print("PLAYWRIGHT CHATGPT -> JSON STRUCTURED IDEA PIPELINE")
    print("=" * 60)

    response_text = fetch_response_via_playwright(PROMPT)
    ideas = parse_json_ideas(response_text)
    print(f"\n[Parsed Ideas Count]: {len(ideas)}")

    saved, csv_path = save_ideas_to_sqlite_and_csv(ideas)
    print(f"\nSuccessfully saved {len(saved)} distinct ideas into separate DB rows!")
    print(f"[CSV Exported Path]: {csv_path}\n")

if __name__ == "__main__":
    run()
