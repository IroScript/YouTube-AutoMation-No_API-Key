r"""
Universal Playwright ChatGPT 10-Level Prompt Escalation Generator & SQLite Saver
================================================================================
Dynamically builds 10-Level Escalation Prompts (10 Image + 10 Video = 20 Prompts)
for ANY Idea from SQLite `ideas` table (Wheat, Corn, Volcano, Moon, etc.) via ChatGPT,
and saves all prompts into `prompts` table in youtube_pipeline.db.
"""

import sys
import os
import re
import json
import uuid
import time
import argparse
from pathlib import Path
from sqlmodel import select

BASE_DIR = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = str(BASE_DIR / "flowboard" / "agent")
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from flowboard.db.youtube_session import init_youtube_db, get_youtube_session
from flowboard.db.youtube_models import Idea, Prompt
from playwright.sync_api import sync_playwright

OUTPUT_TXT_PATH = BASE_DIR / "WebInterfaceChatForPrompts" / "playwright" / "prompts_output.txt"
CHATGPT_URL = "https://chatgpt.com"


def build_escalation_prompt(idea_title: str, idea_description: str, idea_topic: str = "") -> str:
    """Builds a dynamic universal 10-Level prompt instruction for any idea."""
    return f"""
Given the following Impossible Machine Idea:
Title: {idea_title}
Topic/Element: {idea_topic or 'General'}
Concept: {idea_description}

Please build a complete 10-level escalation prompting system (10 Image Prompts + 10 Video Prompts = 20 Prompts total) evolving from Level 1 (BASIC) to Level 10 (ALIEN LEVEL / MAXIMUM).

STRICT RULES FOR EVERY LEVEL (LEVEL 1 TO LEVEL 10):

1. IMAGE PROMPT:
   Must use a 5-Layer Open Montage Structure:
   - Layer 1 (Subject): Core titan machine/megastructure subject for {idea_title}
   - Layer 2 (Environment): {idea_topic or 'Surrounding'} atmosphere & landscape
   - Layer 3 (Architecture): Mechanical chassis, harvester/processor components, and titanic structure
   - Layer 4 (Energy/Physics): Energy fields, glows, magnetic/quantum physics
   - Layer 5 (Cinematic Presentation): Camera framing, photorealistic lighting, cinematic depth, 16k render

2. VIDEO PROMPT (EXACTLY 8 SECONDS):
   Must use the generated image as the first frame / reference image.
   The video MUST break down the machine's operation into 5 MAJOR STEPS during the first 5 seconds (1 step per second), accompanied by a sleek translucent consumer-level HUD message popup text overlay on screen:
   - Second 1 [0:00-0:01]: HUD Popup Text: "STEP 1: [Step Name]" — [Visual action description]
   - Second 2 [0:01-0:02]: HUD Popup Text: "STEP 2: [Step Name]" — [Visual action description]
   - Second 3 [0:02-0:03]: HUD Popup Text: "STEP 3: [Step Name]" — [Visual action description]
   - Second 4 [0:03-0:04]: HUD Popup Text: "STEP 4: [Step Name]" — [Visual action description]
   - Second 5 [0:04-0:05]: HUD Popup Text: "STEP 5: [Step Name]" — [Visual action description]
   - Seconds 6-8 [0:05-0:08]: HUD text fades, camera achieves maximum close-up as machine operation stabilizes.
   Photorealistic cinematic render, smooth continuous motion, no cuts, exactly 8 seconds.

Please generate all 10 Levels numbered 1 to 10 in English:

LEVEL 1 — BASIC
IMAGE 01: [5-Layer Image Prompt]
VIDEO 01: [8s Video Prompt with 5-step HUD text popups]

LEVEL 2 — MORE STRUCTURE
IMAGE 02: [5-Layer Image Prompt]
VIDEO 02: [8s Video Prompt with 5-step HUD text popups]

...

LEVEL 10 — ALIEN LEVEL / MAXIMUM
IMAGE 10: [5-Layer Image Prompt]
VIDEO 10: [8s Video Prompt with 5-step HUD text popups]
""".strip()


def parse_prompts(text: str):
    """Parse output text into 10 levels of image and video prompt pairs."""
    levels_data = []
    level_blocks = re.split(r'LEVEL\s+(\d+)\s*[\—\-–:]\s*([^\n]+)', text, flags=re.IGNORECASE)

    if len(level_blocks) >= 4:
        for i in range(1, len(level_blocks), 3):
            lvl_num = int(level_blocks[i].strip())
            lvl_name = f"Level {lvl_num} - {level_blocks[i+1].strip()}"
            block = level_blocks[i+2]

            img_match = re.search(r'IMAGE\s*\d*\s*[:\-]\s*(.*?)(?=VIDEO|\Z)', block, re.DOTALL | re.IGNORECASE)
            vid_match = re.search(r'VIDEO\s*\d*\s*[:\-]\s*(.*?)(?=LEVEL|\Z)', block, re.DOTALL | re.IGNORECASE)

            img_text = img_match.group(1).strip() if img_match else ""
            vid_text = vid_match.group(1).strip() if vid_match else ""

            if img_text or vid_text:
                levels_data.append({
                    "level": lvl_num,
                    "level_name": lvl_name,
                    "image_prompt": img_text,
                    "video_prompt": vid_text
                })
    return levels_data


def generate_escalation_for_idea(idea_id: int = None, mock_fallback: bool = False, skip_browser: bool = False):
    """Universal function to generate 10-level prompts for ANY idea in SQLite."""
    init_youtube_db()

    with get_youtube_session() as session:
        if idea_id:
            target_idea = session.exec(select(Idea).where(Idea.id == idea_id)).first()
        else:
            # Pick first idea that doesn't have prompts yet, or latest idea
            target_idea = session.exec(select(Idea).order_by(Idea.id.desc())).first()

        if not target_idea:
            print("[Error] No idea found in SQLite `ideas` table!")
            return []

        cur_id = target_idea.id
        idea_title = target_idea.title
        idea_desc = target_idea.description or target_idea.raw_idea or ""
        idea_topic = target_idea.topic or ""

    print(f"\n============================================================")
    print(f"GENERATING 10-LEVEL PROMPTS FOR IDEA: #{cur_id} - '{idea_title}' (Topic: {idea_topic})")
    print(f"============================================================")

    prompt_instruction = build_escalation_prompt(idea_title, idea_desc, idea_topic)

    output_text = ""
    if not skip_browser:
        try:
            print("[Playwright] Launching Chromium browser...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()

                print(f"[Playwright] Navigating to {CHATGPT_URL}...")
                page.goto(CHATGPT_URL, wait_until="networkidle", timeout=60000)
                time.sleep(3)

                prompt_selector = "#prompt-textarea"
                print(f"[Playwright] Waiting for prompt textarea...")
                page.wait_for_selector(prompt_selector, timeout=30000)

                box = page.locator(prompt_selector).first
                box.click()
                box.fill(prompt_instruction)
                time.sleep(1)

                send_btn = page.locator('button[data-testid="send-button"]')
                if send_btn.count() > 0 and send_btn.first.is_visible():
                    send_btn.first.click()
                    print("[Playwright] Clicked send button.")
                else:
                    box.press("Enter")
                    print("[Playwright] Pressed Enter.")

                print("[Playwright] Waiting for ChatGPT response streaming...")
                time.sleep(10)

                max_wait = 120
                elapsed = 0
                while elapsed < max_wait:
                    stop_btn = page.locator('button[data-testid="stop-button"], button[aria-label="Stop streaming"]')
                    if stop_btn.count() == 0 or not stop_btn.first.is_visible():
                        print("[Playwright] Response generation completed!")
                        break
                    time.sleep(3)
                    elapsed += 3

                time.sleep(3)
                responses = page.locator('div[data-message-author-role="assistant"], div.markdown')
                if responses.count() > 0:
                    output_text = responses.last.inner_text()

                with open(OUTPUT_TXT_PATH, "w", encoding="utf-8") as f:
                    f.write(output_text)

                browser.close()
        except Exception as e:
            print(f"[Playwright Notice]: {e}")
    
    if not output_text and (mock_fallback or skip_browser):
        print("[Fallback] Generating mock 10-level escalation structure...")
        mock_lines = []
        for lvl in range(1, 11):
            mock_lines.append(f"LEVEL {lvl} — LEVEL {lvl} ESCALATION")
            mock_lines.append(f"IMAGE {lvl:02d}: Layer 1: Core {idea_title} titan subject. Layer 2: {idea_topic} environment. Layer 3: Titanic chassis architecture. Layer 4: Quantum energy field glows. Layer 5: 16k photorealistic cinematic camera framing.")
            mock_lines.append(f"VIDEO {lvl:02d}: STEP 1: Initialization | STEP 2: Harvester Deployment | STEP 3: Intake Acceleration | STEP 4: Core Processing | STEP 5: Full Output Stabilization. Camera smoothly pans across {idea_title} for 8 seconds.")
        output_text = "\n\n".join(mock_lines)

    if not output_text:
        print("[Error] No output text received.")
        return []

    parsed_levels = parse_prompts(output_text)
    print(f"\n[Parsed Levels Count]: {len(parsed_levels)}")

    with get_youtube_session() as session:
        # Clean existing prompts for this idea
        old_prompts = session.exec(select(Prompt).where(Prompt.idea_id == cur_id)).all()
        for p in old_prompts:
            session.delete(p)
        session.commit()

        saved_count = 0
        for item in parsed_levels:
            lvl = item["level"]
            lvl_name = item["level_name"]

            # Save Image Prompt
            img_prompt = Prompt(
                uuid=str(uuid.uuid4()),
                idea_id=cur_id,
                prompt_type="image_prompt",
                title=f"{idea_title} - {lvl_name} (Image)",
                prompt_text=item["image_prompt"],
                generation_type="image",
                aspect_ratio="16:9",
                level=lvl,
                level_name=lvl_name,
                structure_type="5_layer_montage",
                status="ready"
            )
            session.add(img_prompt)
            session.commit()
            session.refresh(img_prompt)

            # Save Video Prompt
            vid_prompt = Prompt(
                uuid=str(uuid.uuid4()),
                idea_id=cur_id,
                prompt_type="video_prompt",
                title=f"{idea_title} - {lvl_name} (Video 8s)",
                prompt_text=item["video_prompt"],
                generation_type="video",
                duration_seconds=8.0,
                level=lvl,
                level_name=lvl_name,
                structure_type="8s_5_step_hud_popup",
                reference_image_prompt_id=img_prompt.id,
                status="ready"
            )
            session.add(vid_prompt)
            session.commit()
            saved_count += 2

        print(f"[Success] Saved {saved_count} prompts (10 Image + 10 Video) into `prompts` table for Idea #{cur_id} ('{idea_title}')!\n")
        return parsed_levels


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Universal 10-Level Prompt Escalation Generator")
    parser.add_argument("--idea-id", type=int, default=None, help="Target Idea ID from SQLite ideas table")
    parser.add_argument("--mock-fallback", action="store_true", help="Fallback to mock escalation if browser automation is not available")
    parser.add_argument("--skip-browser", action="store_true", help="Skip browser automation and generate structure directly for testing")
    args = parser.parse_args()

    generate_escalation_for_idea(idea_id=args.idea_id, mock_fallback=args.mock_fallback, skip_browser=args.skip_browser)
