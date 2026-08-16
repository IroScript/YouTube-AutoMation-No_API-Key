"""
Playwright ChatGPT Element Idea Generator (Standalone)
======================================================
Generates 10 Giant Impossible Machine Ideas for ANY Element from `elements` table.
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

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.session import get_session, init_db
from database.models import Idea, Element, IdeaElement, Category


def build_element_prompt(element_name: str, element_group: str = "") -> str:
    return f"""
Give me 10 creative impossible machine ideas related to {element_name} (Category/Group: {element_group or 'General'}).
Primary feature: Each machine MUST be giant in size (colossal megastructures, titan-scale, impossible engineering).

CRITICAL FORMATTING INSTRUCTION:
Please return the 10 ideas strictly as a JSON array of 10 objects. Do not include markdown conversational text.

JSON Schema:
[
  {{
    "id": 1,
    "title": "Machine Title",
    "description": "Short 2-3 sentence description of how the giant machine operates on {element_name}."
  }}
]
""".strip()


def parse_json_ideas(response_text: str, element_name: str):
    match = re.search(r'\[\s*\{.*\}\s*\]', response_text, re.DOTALL)
    if match:
        try:
            items = json.loads(match.group(0))
            if isinstance(items, list):
                return items
        except Exception:
            pass

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


def save_element_ideas(element: Element, ideas_list):
    init_db()
    saved_records = []
    with get_session() as session:
        cat = session.exec(select(Category).where(Category.name == "Impossible Giant Machine")).first()
        cat_id = cat.id if cat else 1

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

            idea_elem = IdeaElement(
                idea_id=new_idea.id,
                element_id=element.id,
                is_primary=(idx == 1)
            )
            session.add(idea_elem)
            session.commit()
            saved_records.append({"id": new_idea.id, "title": new_idea.title, "topic": new_idea.topic})

    return saved_records
