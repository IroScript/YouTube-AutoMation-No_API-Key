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
        "system_instruction": "Build 10 escalating levels from Level 1 (BASIC) to Level 10 (ALIEN LEVEL / MAXIMUM). Each level has 1 Image Prompt (5-Layer Open Montage: Subject, Environment, Architecture, Energy/Physics, Cinematic Presentation 16k) + 1 Video Prompt (Exactly 8 seconds, 9:16 vertical ratio, 5-step HUD text popups for seconds 1-5, continuous close-up descent for seconds 6-8). Total 20 prompts. Return strictly JSON array.",
        "prompt_template": """Given the following Impossible Machine Idea:
Title: {idea_title}
Topic/Element: {topic}
Concept: {description}

Please build a complete 10-level escalation prompting system (10 Image Prompts + 10 Video Prompts = 20 Prompts total) evolving from Level 1 (BASIC) to Level 10 (ALIEN LEVEL / MAXIMUM).

STRICT RULES & ARCHITECTURE:
1. IMAGE PROMPT (5-Layer Open Montage Structure, 9:16 vertical aspect ratio, 16K photorealistic render):
   Layer 1 — Subject: Colossal titan machine silhouette, scale, harvesting arms/claws, autonomous drones, sensor crowns.
   Layer 2 — Environment: Continental landscape, thousands of fields/features, tiny vehicles/workers showing scale, atmospheric depth.
   Layer 3 — Architecture: Multi-level torso, processing chambers, threshing cylinders, cyclone separators, drying reactors, storage vaults.
   Layer 4 — Energy/Physics: High-voltage plasma conduits, electromagnetic fields, glowing thermal loops, magnetic suspension.
   Layer 5 — Cinematic Presentation: Dramatic low-angle cinematic framing, 9:16 vertical composition, volumetric lighting, wet-surface reflections, 16K render.

2. VIDEO PROMPT (EXACTLY 8 SECONDS, 9:16 VERTICAL ASPECT RATIO, NO CUTS):
   Must follow this EXACT second-by-second timeline:
   "Exactly 8 seconds, 9:16 vertical aspect ratio, photorealistic cinematic render, smooth continuous motion, no cuts, maximum cinematic realism.

   Second 1 [0:00-0:01] — HUD Popup Text: \\"STEP 1: [ACTION NAME]\\" — [Detailed description of core activation, sensor halos, and systems].

   Second 2 [0:01-0:02] — HUD Popup Text: \\"STEP 2: [ACTION NAME]\\" — [Detailed description of harvesting arms deploying and gathering crops/matter].

   Second 3 [0:02-0:03] — HUD Popup Text: \\"STEP 3: [ACTION NAME]\\" — [Detailed description of processing/threshing streams entering internal belly factories].

   Second 4 [0:03-0:04] — HUD Popup Text: \\"STEP 4: [ACTION NAME]\\" — [Detailed description of quantum/electromagnetic purification, gravity separation, and drying].

   Second 5 [0:04-0:05] — HUD Popup Text: \\"STEP 5: [ACTION NAME]\\" — [Detailed description of cascading storage into vast glowing reservoirs].

   Seconds 6-8 [0:05-0:08]: HUD text completely fades; the camera performs a continuous impossible-scale descent from the cosmic titan into its belly, through alien processing architecture, and finally reaches a maximum close-up of a single harvested particle/grain suspended beside a colossal quantum mechanism, with the surrounding machinery stabilizing into a mesmerizing continuous harvesting rhythm, no cuts, no scene transition, exactly 8 seconds."

CRITICAL FORMATTING INSTRUCTION:
Return strictly a JSON array of 10 objects. Do NOT include markdown conversation outside the JSON.

JSON Schema:
[
  {{
    "level": 1,
    "level_name": "Level 1 - Basic Prototype",
    "image_prompt": "5-Layer Open Montage Structure\\n\\nLayer 1 — Subject: ...\\n\\nLayer 2 — Environment: ...\\n\\nLayer 3 — Architecture: ...\\n\\nLayer 4 — Energy/Physics: ...\\n\\nLayer 5 — Cinematic Presentation: ...",
    "video_prompt": "Exactly 8 seconds, 9:16 vertical aspect ratio, photorealistic cinematic render, smooth continuous motion, no cuts, maximum cinematic realism.\\n\\nSecond 1 [0:00-0:01] — HUD Popup Text: \\"STEP 1: ...\\" — ...\\n\\nSecond 2 [0:01-0:02] — HUD Popup Text: \\"STEP 2: ...\\" — ...\\n\\nSecond 3 [0:02-0:03] — HUD Popup Text: \\"STEP 3: ...\\" — ...\\n\\nSecond 4 [0:03-0:04] — HUD Popup Text: \\"STEP 4: ...\\" — ...\\n\\nSecond 5 [0:04-0:05] — HUD Popup Text: \\"STEP 5: ...\\" — ...\\n\\nSeconds 6-8 [0:05-0:08]: HUD text completely fades; the camera performs a continuous impossible-scale descent from the titan into its belly, through processing architecture, reaching a maximum close-up beside the mechanism, stabilizing into continuous rhythm, no cuts, exactly 8 seconds."
  }}
]""",
        "output_format": "JSON_ARRAY",
        "model_target": "ChatGPT-4o / Playwright",
        "rules_and_constraints": "1. Strict JSON array of 10 level objects. 2. Exactly 20 prompts (10 Image + 10 Video). 3. All video prompts are 9:16 vertical aspect ratio, exactly 8 seconds, no cuts, with Second 1-5 HUD popups and Seconds 6-8 continuous descent close-up. 4. All image prompts use 5-Layer Open Montage."
    },
    {
        "stage_name": "STAGE_4_IMAGE_5LAYER_BLUEPRINT",
        "target_hierarchy_level": "Level 4 (Image Prompt Layer Structure)",
        "style_title": "5-Layer Open Montage Image Blueprint (9:16 Vertical)",
        "system_role": "Cinematic Visual Prompt Engineer",
        "system_instruction": "5 distinct visual layers: Layer 1 (Subject Titan) + Layer 2 (Landscape/Environment) + Layer 3 (Chassis/Materials) + Layer 4 (Quantum Energy Glows) + Layer 5 (16k Photorealistic Framing). 9:16 vertical ratio.",
        "prompt_template": """5-Layer Open Montage Structure

Layer 1 — Subject: Colossal {idea_title} titan machine towering above the terrain, massive articulated harvesting claws, autonomous drone arrays, and multi-sensor crown.

Layer 2 — Environment: Vast continental {topic} landscape extending to horizon, atmospheric clouds, tiny vehicles and structures emphasizing astronomical scale.

Layer 3 — Architecture: Heavy armored chassis, multi-tier belly processing complex, stacked threshing drums, cyclone separation vaults, and glowing modular silos.

Layer 4 — Energy/Physics: Brilliant plasma conduits, electromagnetic flux fields, thermal radiation loops, and localized gravity distortion around mechanical joints.

Layer 5 — Cinematic Presentation: Low-angle IMAX perspective, 9:16 vertical framing, photorealistic volumetric lighting, wet-surface reflections, deep atmospheric depth, 16K render.""",
        "output_format": "STRUCTURED_TEXT",
        "model_target": "Imagen 3 / Midjourney / DALL-E 3",
        "rules_and_constraints": "Must contain all 5 layers explicitly separated for maximum visual depth and photorealism in 9:16 vertical aspect ratio."
    },
    {
        "stage_name": "STAGE_5_VIDEO_8S_HUD_BLUEPRINT",
        "target_hierarchy_level": "Level 4 (Video Prompt Structure - 1Video10Sec / Veo)",
        "style_title": "8-Second 5-Step HUD Popup Video Blueprint (9:16 Vertical)",
        "system_role": "Cinematic Motion & Video Director",
        "system_instruction": "8-second continuous cinematic shot. 9:16 vertical ratio. Seconds 1-5 display 5-step HUD text popups. Seconds 6-8 perform continuous descent and maximum close-up stabilization. No cuts.",
        "prompt_template": """Exactly 8 seconds, 9:16 vertical aspect ratio, photorealistic cinematic render, smooth continuous motion, no cuts, maximum cinematic realism.

Second 1 [0:00-0:01] — HUD Popup Text: "STEP 1: AWAKEN THE TITAN" — The agricultural intelligence activates, illuminating sensor halos and planetary-scale systems across {idea_title}.

Second 2 [0:01-0:02] — HUD Popup Text: "STEP 2: HARVEST REALITY" — Innumerable colossal arms sweep across {topic} terrain and gather resources with synchronized mechanical precision.

Second 3 [0:02-0:03] — HUD Popup Text: "STEP 3: TRANSDIMENSIONAL THRESH" — Entire crop streams enter internal intakes and emerge inside the titan's impossible belly factory.

Second 4 [0:03-0:04] — HUD Popup Text: "STEP 4: QUANTUM PURIFICATION" — Harvested matter floats through gravitational separators, magnetic fields, and drying reactors.

Second 5 [0:04-0:05] — HUD Popup Text: "STEP 5: STORE THE HARVEST UNIVERSE" — Finished yield cascades into an infinite-dimensional storage chamber containing vast glowing reserves.

Seconds 6-8 [0:05-0:08]: HUD text completely fades; the camera performs a continuous impossible-scale descent from the cosmic titan into its belly, through alien processing architecture, and finally reaches a maximum close-up of a single harvested unit suspended beside a colossal quantum mechanism, with the surrounding machinery stabilizing into a mesmerizing continuous harvesting rhythm, no cuts, no scene transition, exactly 8 seconds.""",
        "output_format": "STRUCTURED_TEXT",
        "model_target": "Google Veo 2 / 1Video10Sec",
        "rules_and_constraints": "1. Exactly 8 seconds duration. 2. 9:16 vertical aspect ratio. 3. 5-step HUD overlays during seconds 1-5. 4. Smooth continuous descent in seconds 6-8. 5. Zero cuts or scene transitions."
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
                existing.style_title = item["style_title"]
                existing.target_hierarchy_level = item["target_hierarchy_level"]
                existing.system_role = item["system_role"]
                existing.system_instruction = item["system_instruction"]
                existing.prompt_template = item["prompt_template"]
                existing.output_format = item["output_format"]
                existing.model_target = item["model_target"]
                existing.rules_and_constraints = item["rules_and_constraints"]
                session.add(existing)

        session.commit()

    print(f"[Success] `prompting_style_master` table initialized & seeded with {len(STYLES)} official styles (New: {inserted_count})!")


if __name__ == "__main__":
    seed_prompting_styles()
