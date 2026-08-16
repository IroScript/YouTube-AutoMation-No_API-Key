"""
Seed Prompting Style Master Table
=================================
Initializes and populates `prompting_style_master` table with all official
prompt templates and engineering styles across every level of the pipeline.
"""

import sys
import uuid
from pathlib import Path
from sqlmodel import select

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.session import init_db, get_session
from database.models import PromptingStyleMaster


STYLES = [
    {
        "stage_name": "STAGE_1_ELEMENT_GENERATION",
        "target_hierarchy_level": "Level 1 -> 2 (Category to New Element #101+)",
        "style_title": "Universal Cosmic & Nature Element Generator",
        "system_role": "Senior SciFi Worldbuilder & Megastructure Architect",
        "system_instruction": "Generate creative, highly visual theme/element names suitable for giant impossible machines. Must return strict JSON.",
        "prompt_template": """Give me 1 creative, highly visual theme/element name (like 'Dark Matter Core', 'Neutron Star Forge', 'Cybernetic Hive', 'Liquid Crystal Glacier') suitable for generating giant impossible machines in the category '{category_name}'.
Return strictly JSON format:
{{
  "name": "Element Name",
  "group_type": "Group (Nature/Tech/Environment/Energy/Space)"
}}""",
        "output_format": "JSON_OBJECT",
        "model_target": "ChatGPT-4o / Playwright",
        "rules_and_constraints": "1. Must return strict JSON object with 'name' and 'group_type'. 2. Must be visually unique and scalable for giant engineering."
    },
    {
        "stage_name": "STAGE_2_IDEA_GENERATION",
        "target_hierarchy_level": "Level 2 -> 3 (Element to 10 Machine Ideas)",
        "style_title": "10-Titan Impossible Megastructure Ideation Engine",
        "system_role": "Colossal SciFi Machine Engineer & Visual Concept Designer",
        "system_instruction": "Generate exactly 10 distinct, impossible giant machine ideas for a given element. Each must be colossal/titan scale. Return strictly JSON array.",
        "prompt_template": """Give me 10 creative impossible machine ideas related to {element_name} (Category/Group: {element_group}).
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
]""",
        "output_format": "JSON_ARRAY",
        "model_target": "ChatGPT-4o / Playwright",
        "rules_and_constraints": "1. Return strict JSON array of 10 objects. 2. Every machine must be colossal/planetary scale. 3. Short 2-3 sentence description per idea."
    },
    {
        "stage_name": "STAGE_3_PROMPT_ESCALATION_MASTER",
        "target_hierarchy_level": "Level 3 -> 4 (Idea to 10-Level Escalation Prompts)",
        "style_title": "10-Level Escalation Master Prompt Architecture (Basic to Alien Level)",
        "system_role": "Master SciFi Cinematographer & Prompt Escalation Architect",
        "system_instruction": "Build 10 escalating levels from Level 1 (BASIC) to Level 10 (ALIEN LEVEL / MAXIMUM). Each level has 1 Image Prompt (5-Layer Open Montage) + 1 Video Prompt (8-Second 5-Step HUD Popups). Total 20 prompts.",
        "prompt_template": """Given the following Impossible Machine Idea:
Title: {idea_title}
Topic/Element: {topic}
Concept: {description}

Please build a complete 10-level escalation prompting system (10 Image Prompts + 10 Video Prompts = 20 Prompts total) evolving from Level 1 (BASIC) to Level 10 (ALIEN LEVEL / MAXIMUM).

STRICT RULES:
1. IMAGE PROMPT: 5-Layer Open Montage (Subject, Environment, Architecture, Energy/Physics, Cinematic Presentation 16k).
2. VIDEO PROMPT (EXACTLY 8 SECONDS): 5-step HUD text popups during seconds 1-5 (e.g. 'STEP 1: [Name]'), camera maximum close-up seconds 6-8. Smooth continuous cinematic motion.

Generate all 10 Levels numbered 1 to 10 in English:
LEVEL 1 — BASIC
IMAGE 01: [5-Layer Image Prompt]
VIDEO 01: [8s Video Prompt with 5-step HUD popups]
...
LEVEL 10 — ALIEN LEVEL / MAXIMUM
IMAGE 10: [5-Layer Image Prompt]
VIDEO 10: [8s Video Prompt with 5-step HUD popups]""",
        "output_format": "STRUCTURED_TEXT",
        "model_target": "ChatGPT-4o / Playwright",
        "rules_and_constraints": "1. Exactly 10 levels. 2. 20 prompts (10 Image + 10 Video). 3. Image prompts use 5-Layer Open Montage. 4. Video prompts are exactly 8 seconds with 5-step HUD popups."
    },
    {
        "stage_name": "STAGE_4_IMAGE_5LAYER_BLUEPRINT",
        "target_hierarchy_level": "Level 4 (Image Prompt Layer Structure)",
        "style_title": "5-Layer Open Montage Image Blueprint",
        "system_role": "Cinematic Visual Prompt Engineer",
        "system_instruction": "5 distinct visual layers: Layer 1 (Subject Titan) + Layer 2 (Landscape/Environment) + Layer 3 (Chassis/Materials) + Layer 4 (Quantum Energy Glows) + Layer 5 (16k Photorealistic Framing).",
        "prompt_template": "Layer 1: Core {idea_title} titan subject. Layer 2: {topic} environment. Layer 3: Titanic chassis architecture. Layer 4: Quantum energy field glows. Layer 5: 16k photorealistic cinematic camera framing.",
        "output_format": "STRUCTURED_TEXT",
        "model_target": "Imagen 3 / Midjourney / DALL-E 3",
        "rules_and_constraints": "Must contain all 5 layers explicitly separated for maximum visual depth and photorealism."
    },
    {
        "stage_name": "STAGE_5_VIDEO_8S_HUD_BLUEPRINT",
        "target_hierarchy_level": "Level 4 (Video Prompt Structure - 1Video10Sec / Veo)",
        "style_title": "8-Second 5-Step HUD Popup Video Blueprint",
        "system_role": "Cinematic Motion & Video Director",
        "system_instruction": "8-second continuous cinematic shot. Seconds 1-5 display 5-step HUD text popups. Seconds 6-8 perform maximum close-up pan and stabilization.",
        "prompt_template": "STEP 1: Core Startup | STEP 2: Harvester Deployment | STEP 3: Intake Acceleration | STEP 4: Processing Wave | STEP 5: Full Output Stabilization. Camera smoothly pans across {idea_title} for 8 seconds.",
        "output_format": "STRUCTURED_TEXT",
        "model_target": "Google Veo 2 / 1Video10Sec",
        "rules_and_constraints": "1. Exactly 8 seconds duration. 2. 5-step HUD overlays during seconds 1-5. 3. Smooth cinematic movement in seconds 6-8."
    },
    {
        "stage_name": "STAGE_6_YOUTUBE_METADATA",
        "target_hierarchy_level": "Level 5 (Output Package & YouTube SEO)",
        "style_title": "High-CTR YouTube Metadata & SEO Optimizer",
        "system_role": "Viral YouTube Growth & SEO Strategist",
        "system_instruction": "Generate viral, curiosity-driven YouTube Title (<80 chars + 1 emoji), 3-paragraph SEO description with timestamps and 5 hashtags, and 10-15 search tags in JSON.",
        "prompt_template": """Given the following AI-generated impossible giant machine video:
Video Subject: {idea_title}
Topic/Element: {topic}
Escalation Level: {level_info}

Please generate a professional YouTube metadata package in strict JSON format:
{{
  "title": "A high-CTR, curiosity-driven YouTube video title (under 80 chars, with 1 emoji)",
  "seo_description": "A 3-paragraph SEO-rich video description with timecodes, storyline breakdown, and 5 hashtags (#AI #Megastructure #Veo #SciFi #ImpossibleEngineering)",
  "tags": ["10-15 viral search tags as array of strings"],
  "category": "Science & Technology",
  "default_language": "en"
}}
Return ONLY the raw JSON object.""",
        "output_format": "JSON_OBJECT",
        "model_target": "ChatGPT-4o / Playwright",
        "rules_and_constraints": "1. High-CTR title with emoji. 2. 3-paragraph description with timestamps. 3. 5 viral hashtags. 4. Strict JSON format."
    }
]


def seed_prompting_styles():
    init_db()
    inserted_count = 0
    with get_session() as session:
        for item in STYLES:
            existing = session.exec(select(PromptingStyleMaster).where(
                PromptingStyleMaster.stage_name == item["stage_name"]
            )).first()

            if not existing:
                record = PromptingStyleMaster(
                    uuid=str(uuid.uuid4()),
                    stage_name=item["stage_name"],
                    target_hierarchy_level=item["target_hierarchy_level"],
                    style_title=item["style_title"],
                    system_role=item["system_role"],
                    system_instruction=item["system_instruction"],
                    prompt_template=item["prompt_template"],
                    output_format=item["output_format"],
                    model_target=item["model_target"],
                    rules_and_constraints=item["rules_and_constraints"],
                    is_active=1,
                    version=1
                )
                session.add(record)
                inserted_count += 1
            else:
                existing.prompt_template = item["prompt_template"]
                existing.system_role = item["system_role"]
                existing.system_instruction = item["system_instruction"]
                existing.rules_and_constraints = item["rules_and_constraints"]
                session.add(existing)

        session.commit()

    print(f"[Success] `prompting_style_master` table initialized & seeded with {len(STYLES)} official styles (New: {inserted_count})!")


if __name__ == "__main__":
    seed_prompting_styles()
