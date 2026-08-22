import os
import sys
import json
import re
import time
from pathlib import Path

BASE_DIR = Path(r"C:\Users\Irak\Desktop\Youtube Pipeline\PromptDatabase")
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import cloakbrowser
from database.session import init_db, get_session
from database.models import Idea, Element, IdeaElement
from sqlmodel import select

def build_enrichment_prompt(element_name: str, element_group: str, ideas_subset: list) -> str:
    ideas_text = "\n".join([f"- Idea #{ida.id}: '{ida.title}' (Current core: {ida.raw_idea})" for ida in ideas_subset])
    return f"""You are a Lead Sci-Fi Worldbuilder & Colossal Megastructure Concept Engineer.
For the Element '{element_name}' (Category: '{element_group or "Agriculture/Nature"}'), expand each of the following Impossible Machine ideas into a deep, rich, comprehensive 300-to-400-word engineering concept description:

{ideas_text}

For EACH machine idea, write an immersive 300 to 400-word description containing:
1. Mechanical Anatomy & Chassis: Colossal frame, articulated joints, locomotive legs/tracks, specialized cutting/harvesting/manipulation arms.
2. Operational Engineering Workflow: Step-by-step physical processing, material extraction, and continuous interaction with {element_name}.
3. Internal Belly Factory Architecture: Multi-level processing galleries, cyclone separation cylinders, drying chambers, and storage vaults.
4. Energy, Physics & Sci-Fi Principles: Plasma conduits, magnetic suspension fields, quantum gravity manipulation, and thermal exhaust systems.
5. Atmospheric Scale & World Interaction: Planetary-scale visual presence, comparisons to mountains/skyscrapers, and weather interaction.

CRITICAL FORMATTING INSTRUCTION:
Return strictly a valid JSON array of objects. Do not include introductory or concluding conversational text.
JSON Schema:
[
  {{
    "id": <idea_id>,
    "title": "<idea_title>",
    "description": "<300-to-400-word deep machine engineering concept description>"
  }}
]"""

def extract_ideas_from_response(raw_text: str) -> list[dict]:
    if not raw_text:
        return []
    # Try direct JSON array match
    match = re.search(r'\[\s*\{.*\}\s*\]', raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    # Fallback to individual JSON objects
    results = []
    for obj_match in re.finditer(r'\{[^{}]*"id"\s*:\s*(\d+)[^{}]*"description"\s*:\s*"([^"]+)"[^{}]*\}', raw_text, re.DOTALL):
        try:
            results.append({
                "id": int(obj_match.group(1)),
                "description": obj_match.group(2)
            })
        except Exception:
            pass
    return results

def enrich_ideas_for_element(element_id: int, max_ideas_per_batch: int = 5, skip_browser: bool = False):
    init_db()
    with get_session() as session:
        elem = session.get(Element, element_id)
        if not elem:
            print(f"[Error] Element #{element_id} not found.")
            return

        links = session.exec(select(IdeaElement).where(IdeaElement.element_id == elem.id)).all()
        idea_ids = [l.idea_id for l in links]
        ideas = session.exec(select(Idea).where(Idea.id.in_(idea_ids))).all()

    print(f"\n================================================================================")
    print(f"🚀 ENRICHING IDEAS FOR ELEMENT #{elem.id}: '{elem.name}' ({len(ideas)} Ideas)")
    print(f"================================================================================")

    # Filter only ideas that still need 300+ word enrichment (< 200 words)
    unfilled_ideas = [ida for ida in ideas if len((ida.description or ida.raw_idea or "").split()) < 200]
    if not unfilled_ideas:
        print(f"  [All Enriched] All {len(ideas)} ideas for Element #{elem.id} already have 300+ words!")
        return

    print(f"  -> {len(unfilled_ideas)}/{len(ideas)} ideas need 300+ word expansion.")

    # Process in batches of 5 to allow ChatGPT to comfortably write 300-400 words per idea
    for i in range(0, len(unfilled_ideas), max_ideas_per_batch):
        batch = unfilled_ideas[i:i + max_ideas_per_batch]
        print(f"\n[Batch {i//max_ideas_per_batch + 1}] Processing {len(batch)} Ideas: {[b.title for b in batch]}")

        prompt_text = build_enrichment_prompt(elem.name, elem.group_type, batch)

        if not skip_browser:
            from prompt_chain_engine import call_chatgpt_playwright
            response = call_chatgpt_playwright(prompt_text, wait_seconds=300)
        else:
            response = ""

        enriched_list = extract_ideas_from_response(response)
        print(f"[Parser] Extracted {len(enriched_list)} enriched idea descriptions.")

        # Update database
        with get_session() as session:
            for item in enriched_list:
                ida_id = item.get("id")
                desc = item.get("description", "")
                if ida_id and desc and len(desc.split()) >= 100:
                    db_idea = session.get(Idea, ida_id)
                    if db_idea:
                        db_idea.description = desc.strip()
                        db_idea.raw_idea = desc.strip()
                        session.add(db_idea)
                        word_count = len(desc.split())
                        print(f"  ✅ Updated Idea #{db_idea.id} '{db_idea.title}' -> {word_count} words in database!")
            session.commit()

        # Refresh CSVs
        try:
            from generate_master_joined_csv import generate_master_joined_csv, export_all_tables_to_csv
            generate_master_joined_csv()
            export_all_tables_to_csv()
        except Exception as e:
            print(f"[Notice] CSV export notice: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Enrich Ideas with 300-400 word concept descriptions.")
    parser.add_argument("--element", type=int, default=1, help="Element ID to enrich (default 1).")
    parser.add_argument("--all", action="store_true", help="Enrich all elements with ideas.")
    parser.add_argument("--skip-browser", action="store_true", help="Skip browser for dry test.")
    args = parser.parse_args()

    if args.all:
        init_db()
        with get_session() as s:
            elements = s.exec(select(Element)).all()
        for el in elements:
            enrich_ideas_for_element(el.id, skip_browser=args.skip_browser)
    else:
        enrich_ideas_for_element(args.element, skip_browser=args.skip_browser)
