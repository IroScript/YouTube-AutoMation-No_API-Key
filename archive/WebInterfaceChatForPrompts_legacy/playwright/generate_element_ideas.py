r"""
Universal Playwright ChatGPT Element Idea Generator & SQLite Saver
===================================================================
Dynamically generates 10 Giant Impossible Machine / Concept Ideas from ChatGPT
for ANY Element stored in the SQLite `elements` table (e.g. Paddy, Wheat, Corn, Volcano, etc.),
saves each idea into distinct rows in `ideas` table, and links them in `idea_elements`.
"""

import os
import re
import sys
import json
import time
import uuid
import argparse
from pathlib import Path
from sqlmodel import select

BASE_DIR = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = str(BASE_DIR / "flowboard" / "agent")
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from flowboard.db.youtube_session import get_youtube_session, init_youtube_db
from flowboard.db.youtube_models import Idea, Element, IdeaElement, Category
from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "output.txt")


def build_element_prompt(element_name: str, element_group: str = "") -> str:
    """Builds a dynamic universal ChatGPT prompt for any element."""
    return f"""
Give me 10 creative impossible machine ideas related to {element_name} (Category/Group: {element_group or 'General'}).
Primary feature: Each machine MUST be giant in size (colossal megastructures, titan-scale, impossible engineering).

CRITICAL FORMATTING INSTRUCTION:
Please return the 10 ideas strictly as a JSON array of 10 objects. Do not include any markdown conversational text before or after the JSON.

JSON Schema:
[
  {{
    "id": 1,
    "title": "Machine Title",
    "description": "Short 2-3 sentence description of how the giant machine operates on {element_name}."
  }}
]
""".strip()


def fetch_ideas_via_playwright(prompt_text: str, url: str = "https://chatgpt.com") -> str:
    """Automates ChatGPT via Playwright to fetch responses."""
    print(f"[Playwright] Launching browser to prompt ChatGPT...")
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


def parse_json_ideas(response_text: str, element_name: str):
    """Parses JSON response into 10 separate idea dictionaries."""
    match = re.search(r'\[\s*\{.*\}\s*\]', response_text, re.DOTALL)
    if match:
        try:
            items = json.loads(match.group(0))
            if isinstance(items, list):
                return items
        except Exception as e:
            print(f"[JSON Parse Note]: Standard json parse failed ({e}). Fallback to regex.")

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


def save_element_ideas_to_sqlite(element: Element, ideas_list):
    """Saves ideas to SQLite linked to the given element."""
    init_youtube_db()

    with get_youtube_session() as session:
        cat = session.exec(select(Category).where(Category.name == "Impossible Giant Machine")).first()
        cat_id = cat.id if cat else 1

        saved_records = []
        for idx, item in enumerate(ideas_list, 1):
            title = item.get("title", f"{element.name} Machine Idea #{idx}")
            desc = item.get("description", "")

            new_idea = Idea(
                uuid=str(uuid.uuid4()),
                title=title,
                short_title=title,
                raw_idea=f"{title}\n{desc}",
                description=desc,
                category_id=cat_id,
                category="Impossible Giant Machine",
                topic=element.name,
                niche=f"{element.group_type or 'General'} Titan Megastructures",
                status="new",
                priority=idx
            )
            session.add(new_idea)
            session.commit()
            session.refresh(new_idea)

            # Link in idea_elements
            idea_elem = IdeaElement(
                idea_id=new_idea.id,
                element_id=element.id,
                is_primary=True
            )
            session.add(idea_elem)
            session.commit()
            session.refresh(new_idea)
            saved_records.append({"id": new_idea.id, "title": new_idea.title, "topic": new_idea.topic})

    return saved_records


def generate_ideas_for_element(element_id: int = None, element_name: str = None, mock_if_no_browser: bool = False):
    """Universal function to generate 10 ideas for ANY element from SQLite."""
    init_youtube_db()

    with get_youtube_session() as session:
        if element_id:
            element = session.exec(select(Element).where(Element.id == element_id)).first()
        elif element_name:
            element = session.exec(select(Element).where(Element.name.ilike(f"%{element_name}%"))).first()
        else:
            element = session.exec(select(Element).where(Element.id == 1)).first()

        if not element:
            print(f"[Error] No element found for ID={element_id} or Name={element_name}!")
            return []

    print(f"\n============================================================")
    print(f"GENERATING 10 IDEAS FOR ELEMENT: [{element.id}] {element.name} ({element.group_type})")
    print(f"============================================================")

    prompt = build_element_prompt(element.name, element.group_type)

    response_text = ""
    try:
        response_text = fetch_ideas_via_playwright(prompt)
    except Exception as e:
        print(f"[Playwright Notice]: {e}")
        if mock_if_no_browser:
            print(f"[Fallback]: Using structured mock data for element {element.name}...")
            mock_ideas = [
                {"id": i, "title": f"{element.name} Titan Megastructure {i}", "description": f"A colossal planetary-scale machine operating on {element.name} with automated harvesters and quantum energy fields."}
                for i in range(1, 11)
            ]
            response_text = json.dumps(mock_ideas)

    if not response_text:
        print("[Error] No response obtained.")
        return []

    ideas = parse_json_ideas(response_text, element.name)
    saved = save_element_ideas_to_sqlite(element, ideas)
    print(f"[Success] Saved {len(saved)} ideas for element '{element.name}' into SQLite database (linked in idea_elements)!\n")
    return saved


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Universal Element Idea Generator for SQLite")
    parser.add_argument("--element-id", type=int, default=None, help="Element ID from SQLite elements table")
    parser.add_argument("--element-name", type=str, default=None, help="Element Name (e.g. 'Wheat Field', 'Corn Field', 'Volcano')")
    parser.add_argument("--mock-fallback", action="store_true", help="Fallback to mock data if browser automation is unavailable")
    args = parser.parse_args()

    generate_ideas_for_element(element_id=args.element_id, element_name=args.element_name, mock_if_no_browser=args.mock_fallback)
