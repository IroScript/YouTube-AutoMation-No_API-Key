r"""
Prompt Chain Engine - Standalone Backward Dependency Pipeline (No Flowboard)
============================================================================
Hierarchical Architecture:
  Level 1 (Root):   categories table (e.g. 'Impossible Giant Machine')
  Level 2:          elements table (100 Elements, dynamically generates Element #101+ when exhausted)
  Level 3:          ideas table (10 Impossible Machine Ideas per Element, linked via idea_elements)
  Level 4:          prompts table (10-Level Escalation: 10 Image + 10 Video Prompts = 20 Prompts per Idea)
  Level 5 (Output): Level 10 Prompt -> Direct Video Generation (.mp4) via 1Video10Sec + YouTube Metadata JSON

Backward Dependency Checking Logic (Lazy / Just-In-Time Pipeline):
  Goal: Find or generate the next Production-Ready Level 10 Prompt for Video Generation.
  1. Check: Is there an existing Level 10 Video Prompt not yet completed/packaged?
     -> YES: Return it immediately (Ready for Video Generation).
     -> NO: Check if there is an Idea without Level 1-10 Prompts.
  2. If Idea exists without Prompts:
     -> Auto-generate 10-Level Escalation Prompts (10 Image + 10 Video) via Playwright ChatGPT.
     -> Return Level 10 Prompt (Ready).
  3. If all current Ideas have Prompts:
     -> Find an Element without 10 Ideas in SQLite.
     -> If Element exists -> Auto-generate 10 Ideas via Playwright ChatGPT -> Link to Element -> Pick Idea #1 -> Auto-generate 10-Level Escalation Prompts.
     -> Return Level 10 Prompt (Ready).
  4. If all 100 Elements have been fully consumed:
     -> Fetch Category from categories table -> Auto-generate Element #101 via Playwright ChatGPT.
     -> Insert Element -> Generate 10 Ideas -> Generate Escalation -> Return Level 10 Prompt (Ready).
"""

import os
import re
import sys
import json
import uuid
import time
import argparse
from pathlib import Path
from sqlmodel import select

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.session import init_db, get_session
from database.models import Category, Element, Idea, IdeaElement, Prompt, Task, TaskAttempt, GeneratedVideo, PromptingStyleMaster

CHATGPT_URL = "https://chatgpt.com"
OUTPUT_DIR = BASE_DIR / "output_packaged"


def get_prompt_style(stage_name: str) -> PromptingStyleMaster:
    """Fetches official prompt style and template from `prompting_style_master` table."""
    init_db()
    with get_session() as session:
        style = session.exec(select(PromptingStyleMaster).where(
            PromptingStyleMaster.stage_name == stage_name,
            PromptingStyleMaster.is_active == 1
        )).first()
        return style


# ============================================================================
# 1. PLAYWRIGHT / CLOAKBROWSER INTERACTION HELPERS
# ============================================================================

def call_chatgpt_playwright(prompt_text: str, wait_seconds: int = 240, headless: bool = False) -> str:
    """Executes prompt on ChatGPT via CloakBrowser / Playwright anti-detect stealth automation."""
    print(f"\n[CloakBrowser] Launching stealth anti-detect Chrome browser window (Full Screen)...", flush=True)
    output_text = ""
    context = None
    try:
        import cloakbrowser
        context = cloakbrowser.launch_context(
            headless=headless,
            no_viewport=True,
            args=["--start-maximized"]
        )
    except Exception as e:
        print(f"[Notice] Falling back to standard Playwright context: {e}", flush=True)
        from playwright.sync_api import sync_playwright
        p = sync_playwright().start()
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
        )
        context = browser.new_context(no_viewport=True)

    try:
        page = context.new_page()
        print(f"[CloakBrowser] Navigating to {CHATGPT_URL}...", flush=True)
        page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=45000)
        time.sleep(3)

        # Dismiss any overlay / login prompts if present
        for dismiss_sel in ["button:has-text('Stay logged out')", "button:has-text('Dismiss')", "button[aria-label='Close']"]:
            try:
                if page.locator(dismiss_sel).count() > 0 and page.locator(dismiss_sel).first.is_visible():
                    page.locator(dismiss_sel).first.click()
                    time.sleep(1)
            except Exception:
                pass

        # Locate the VISIBLE input element (skipping hidden fallback textareas)
        input_box = None
        for attempt in range(15):
            candidates = page.locator(
                'textarea:visible:not(.wcDTda_fallbackTextarea), '
                '#prompt-textarea:visible, '
                'div[contenteditable="true"]:visible, '
                'textarea#mobile-composer-prompt:visible, '
                'textarea.wm-composer-textarea:visible, '
                '[role="textbox"]:visible'
            )
            if candidates.count() > 0:
                input_box = candidates.first
                break
            time.sleep(1)

        if not input_box:
            raise RuntimeError("No visible input element found on ChatGPT.")

        # Focus & fill
        input_box.click()
        time.sleep(0.3)
        input_box.fill(prompt_text)
        time.sleep(1.0)

        # Click the active send button
        send_btn = page.locator('button.composer-submit-btn:visible, button[aria-label*="Send" i]:visible, button[data-testid="send-button"]:visible, button[aria-label*="Submit" i]:visible').first
        send_btn.click()
        print("[CloakBrowser] Clicked Send button successfully!", flush=True)

        print(f"[CloakBrowser] Waiting for ChatGPT response to stream completely (max {wait_seconds}s)...", flush=True)
        
        # 1. Wait for stream to start
        started = False
        for sec in range(30):
            time.sleep(1.5)
            res = page.evaluate('''() => {
                const stopBtn = document.querySelector('button[aria-label*="Stop" i], button[data-testid*="stop" i]');
                const isStop = stopBtn !== null && stopBtn.offsetParent !== null;
                const turns = document.querySelectorAll('div[data-message-author-role="assistant"]');
                const lastTurn = turns.length > 0 ? turns[turns.length - 1] : null;
                const text = lastTurn ? (lastTurn.innerText || '') : '';
                return { length: text.length, isStop: isStop };
            }''')
            if res['length'] > 0 or res['isStop']:
                print(f"[CloakBrowser] Stream started at {sec*1.5}s! (chars={res['length']}, isStop={res['isStop']})", flush=True)
                started = True
                break

            # If not started after 5s, retry clicking send button only if stop button is not present
            if sec == 3 and not res['isStop']:
                try:
                    s_btn = page.locator('button[aria-label*="Send" i]:visible, button[data-testid="send-button"]:visible').first
                    if s_btn.count() > 0 and not s_btn.is_disabled():
                        s_btn.click()
                except Exception:
                    pass

        if not started:
            print("[CloakBrowser Warning] Stream did not start within 30s. Exiting for immediate retry.", flush=True)
            return ""

        # 2. Instant non-blocking DOM monitoring loop
        last_len = 0
        stable_count = 0
        elapsed = 0
        while elapsed < wait_seconds:
            time.sleep(2)
            elapsed += 2

            snap = page.evaluate('''() => {
                const stopBtn = document.querySelector('button[aria-label*="Stop" i], button[data-testid*="stop" i]');
                const isStop = stopBtn !== null && stopBtn.offsetParent !== null;
                const turns = document.querySelectorAll('div[data-message-author-role="assistant"]');
                const lastTurn = turns.length > 0 ? turns[turns.length - 1] : null;
                const text = lastTurn ? (lastTurn.innerText || '') : '';
                return { isStop: isStop, length: text.length, text: text };
            }''')
            curr_len = snap['length']
            curr_text = snap['text']
            is_stop = snap['isStop']

            if curr_len > last_len:
                stable_count = 0
                last_len = curr_len
                print(f"[CloakBrowser] Streaming in progress... ({curr_len} chars)", flush=True)
            elif curr_len > 100:
                stable_count += 1

            has_level_10 = ('"level": 10' in curr_text or '"level":10' in curr_text or 'Level 10' in curr_text or 'LEVEL 10' in curr_text)
            if (has_level_10 and not is_stop) or (curr_len > 25000 and not is_stop) or (curr_len > 5000 and not is_stop and stable_count >= 3):
                output_text = curr_text
                print(f"[CloakBrowser] Response generation completed successfully! ({curr_len} chars)", flush=True)
                break

        if not output_text and curr_len > 0:
            output_text = curr_text

        if not output_text and curr_len > 0:
            output_text = curr_text
    finally:
        if context:
            try:
                context.close()
                print("[CloakBrowser] Browser window closed cleanly.", flush=True)
            except Exception:
                pass

    return output_text


# ============================================================================
# 2. GENERATION WORKERS FOR EACH HIERARCHICAL LEVEL
# ============================================================================

def generate_new_element_from_category(category_name: str, skip_browser: bool = False) -> Element:
    """Level 1 -> Level 2: Generates a brand new Element (e.g. #101+) when all 100 are consumed."""
    init_db()
    with get_session() as session:
        current_count = len(session.exec(select(Element)).all())
        next_index = current_count + 1

    print(f"\n[Hierarchy Step 1 -> 2] Generating Element #{next_index} for Category '{category_name}'...")
    style = get_prompt_style("STAGE_1_ELEMENT_GENERATION")
    if style:
        prompt_text = style.prompt_template.format(category_name=category_name)
    else:
        prompt_text = f"Give me 1 creative theme/element name for '{category_name}'. Return strictly JSON: {{\"name\": \"...\", \"group_type\": \"...\"}}"

    name = f"Cosmic Element #{next_index}"
    group_type = "Cosmic/Tech"

    if not skip_browser:
        try:
            resp = call_chatgpt_playwright(prompt_text, wait_seconds=45)
            match = re.search(r'\{.*\}', resp, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                name = data.get("name", name)
                group_type = data.get("group_type", group_type)
        except Exception as e:
            print(f"[Notice] Playwright element generation notice: {e}")

    with get_session() as session:
        new_elem = Element(
            uuid=str(uuid.uuid4()),
            name=name,
            group_type=group_type
        )
        session.add(new_elem)
        session.commit()
        session.refresh(new_elem)
        print(f"[Success] Inserted new Element #{new_elem.id}: '{new_elem.name}' ({new_elem.group_type}) into `elements` table.")
        return new_elem


def generate_ideas_for_element(element: Element, skip_browser: bool = False, target_total: int = 10) -> list[Idea]:
    """Level 2 -> Level 3: Generates remaining Impossible Machine Ideas for an Element up to target_total (default 10)."""
    init_db()
    with get_session() as session:
        existing_links = session.exec(select(IdeaElement).where(IdeaElement.element_id == element.id)).all()
        existing_count = len(existing_links)

    needed_count = max(0, target_total - existing_count)
    if needed_count == 0:
        with get_session() as session:
            existing_idea_ids = [l.idea_id for l in existing_links]
            return session.exec(select(Idea).where(Idea.id.in_(existing_idea_ids))).all()

    print(f"\n[Hierarchy Step 2 -> 3] Generating {needed_count} Machine Ideas for Element #{element.id}: '{element.name}' (Existing: {existing_count}/{target_total})...")
    
    style = get_prompt_style("STAGE_2_IDEA_GENERATION")
    if style:
        prompt_text = style.prompt_template.format(element_name=element.name, element_group=element.group_type or 'General')
        if needed_count != 10:
            prompt_text = prompt_text.replace("Give me 10 creative", f"Give me {needed_count} creative")
            prompt_text = prompt_text.replace("10 ideas strictly", f"{needed_count} ideas strictly")
    else:
        prompt_text = f"Give me {needed_count} creative impossible machine ideas related to {element.name}. Return JSON array."

    ideas_data = []
    if not skip_browser:
        try:
            resp = call_chatgpt_playwright(prompt_text, wait_seconds=60)
            match = re.search(r'\[\s*\{.*\}\s*\]', resp, re.DOTALL)
            if match:
                ideas_data = json.loads(match.group(0))
        except Exception as e:
            print(f"[Notice] Playwright idea generation notice: {e}")

        if not ideas_data:
            print(f"[Error] ChatGPT did not return valid ideas for Element #{element.id}. Keeping element unfilled for retry.")
            return []
    else:
        # Offline test generation only when --skip-browser is explicitly passed
        ideas_data = [
            {
                "id": existing_count + i,
                "title": f"The {element.name} Titan Megastructure #{existing_count + i}",
                "description": f"A colossal titan-scale machine operating on {element.name} using automated extraction arms and quantum planetary energy conduits."
            }
            for i in range(1, needed_count + 1)
        ]

    saved_ideas = []
    with get_session() as session:
        cat = session.exec(select(Category).where(Category.name == "Impossible Giant Machine")).first()
        cat_id = cat.id if cat else 1

        for idx, item in enumerate(ideas_data, existing_count + 1):
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
            saved_ideas.append(new_idea)

        saved_ids = [i.id for i in saved_ideas]
        if saved_ids:
            print(f"[Success] Inserted {len(saved_ids)} new ideas for '{element.name}' into `ideas` table (IDs: {saved_ids[0]} to {saved_ids[-1]}). Total linked: {existing_count + len(saved_ids)}/{target_total}.")
    return saved_ideas


def build_rich_escalation_system(idea_title: str, topic: str, description: str = "") -> list[dict]:
    """Generates complete, photorealistic 10-level escalation system with 5-layer image and second-by-second 9:16 8s HUD video prompts."""
    clean_topic = topic if topic and topic.strip() else "Industrial Resource"
    clean_title = idea_title if idea_title and idea_title.strip() else f"{clean_topic} Colossal Titan"
    
    tiers = [
        {
            "level": 1,
            "name": "Level 1 - Basic Industrial Harvester Prototype",
            "img_subj": f"A skyscraper-sized walking {clean_title} prototype, a heavy industrial mechanical titan standing tall above the {clean_topic} landscape, two massive articulated harvesting cranes sweeping through raw terrain, exposed pneumatic joints and industrial cutting claws.",
            "img_env": f"Vast local {clean_topic} terrain extending toward the horizon, misty morning atmosphere, miniature tractors, trucks, and human operators emphasizing the machine's towering scale.",
            "img_arch": f"Heavy reinforced steel chassis, belly-mounted mechanical threshing chamber, visible conveyor belts, basic cyclone separators, and integrated storage silos.",
            "img_eng": f"Subtle diesel-hydraulic exhaust pulses, amber internal machinery illumination, high-tension pneumatic pressure lines, dust and debris displacement around massive iron feet.",
            "img_cin": f"Ultra-wide low-angle establishing shot, 9:16 vertical composition, realistic morning rim light, wet surface reflections, deep volumetric haze, 16K photorealistic render.",
            "s1_hud": "STEP 1: INITIALIZE PRIMARY SYSTEMS",
            "s1_desc": f"Diesel-hydraulic turbine whirs to life, illuminating mechanical status lamps and deployment gauges across {clean_title}.",
            "s2_hud": "STEP 2: DEPLOY HARVEST CRANES",
            "s2_desc": f"Two heavy mechanical harvesting limbs unfold and sweep through the {clean_topic} field with high-torque precision.",
            "s3_hud": "STEP 3: MECHANICAL INTAKE FEED",
            "s3_desc": f"Conveyor belts draw raw harvested yield directly into the titan's primary central processing hopper.",
            "s4_hud": "STEP 4: CYCLONE SEPARATION",
            "s4_desc": f"Internal rotating drums spin rapidly, separating raw {clean_topic} materials from chaff and coarse particulate.",
            "s5_hud": "STEP 5: CONVEYOR SILO LOAD",
            "s5_desc": f"Automated bucket elevators transfer processed yield into heavy reinforced torso silos.",
            "s68_desc": f"HUD text completely fades; camera glides downward into the belly housing and finishes on a maximum macro close-up of rotating steel separation gears with individual {clean_topic} particles flowing smoothly, machinery stabilizing into steady industrial rhythm, no cuts, no scene transition, exactly 8 seconds."
        },
        {
            "level": 2,
            "name": "Level 2 - Reinforced Multi-Limb Mega Harvester",
            "img_subj": f"An advanced multi-story {clean_title} with four reinforced harvesting limbs, high-speed rotary cutting disks, sensor towers, and heavy mechanical stride legs straddling wide terrain sectors.",
            "img_env": f"Interconnected regional {clean_topic} terraces, access roads, industrial canals, hundreds of tiny vehicles showing massive scale, bright sunrise rim lighting.",
            "img_arch": f"Layered armored chassis, exposed structural trusses, multi-stage centrifugal separators, automated dryers, grain elevators, and robotic maintenance arms.",
            "img_eng": f"Synchronized hydraulic actuators, bright cyan status conduits, rotating magnetic separation coils, thermal exhaust shimmers, and mechanical vibration waves.",
            "img_cin": f"Dramatic three-quarter low-angle perspective, 9:16 vertical framing, morning sun lens flare, deep atmospheric perspective, intricate surface textures, 16K render.",
            "s1_hud": "STEP 1: POWER GRID SYNC",
            "s1_desc": f"Sensor masts calibrate and project targeting grids across multiple {clean_topic} zones.",
            "s2_hud": "STEP 2: SYNCHRONIZED SWEEP",
            "s2_desc": f"Four articulated limbs perform coordinated high-speed harvesting arcs across separate field sectors.",
            "s3_hud": "STEP 3: CENTRIFUGAL PROCESSING",
            "s3_desc": f"Multiple internal threshing modules activate in parallel, digesting high-volume intake streams.",
            "s4_hud": "STEP 4: DUAL-STAGE PURIFICATION",
            "s4_desc": f"High-velocity airflow and magnetic sieves isolate pure {clean_topic} matter while thermal chambers dry the stream.",
            "s5_hud": "STEP 5: MULTI-SILO DISTRIBUTION",
            "s5_desc": f"High-speed vertical augers distribute refined harvest across four pressurized torso vaults.",
            "s68_desc": f"HUD text completely fades; camera moves continuously into the multi-stage intake duct and lands on an extreme close-up of a high-speed centrifugal sieve with pure {clean_topic} flowing steadily, operation stabilizing into continuous cadence, no cuts, no scene transition, exactly 8 seconds."
        },
        {
            "level": 3,
            "name": "Level 3 - Continental Megastructure Harvester",
            "img_subj": f"A mountain-sized walking {clean_title} megastructure towering above entire valleys, six colossal hydraulic harvesting gantries, autonomous support crawlers, and heavy planetary tracks.",
            "img_env": f"An immense continental {clean_topic} basin under stormy skies, lightning flashes illuminating the titan's silhouette, tiny villages and roads dwarfed by giant chassis columns.",
            "img_arch": f"Cathedral-sized belly processing complex, stacked cyclone towers, thermal drying reactors, refrigerated vault sectors, automated robotic repair bays.",
            "img_eng": f"High-voltage blue plasma conduits, electromagnetic particle accelerators, localized magnetic guidance fields, intense hydraulic pulses, and ionized air haze.",
            "img_cin": f"Monumental low-angle IMAX composition, 9:16 vertical ratio, dramatic storm lighting, rain and mist reflections on metallic plating, 16K render.",
            "s1_hud": "STEP 1: DEPLOY HARVEST GANTRIES",
            "s1_desc": f"Six colossal hydraulic gantries unlock from the titan's shoulders with immense steam venting.",
            "s2_hud": "STEP 2: MASS CONTINENTAL EXTRACTION",
            "s2_desc": f"Rotating intake heads gather massive continuous waves of {clean_topic} and funnel them into armored intake portals.",
            "s3_hud": "STEP 3: BELLY FACTORY THRESH",
            "s3_desc": f"Massive internal cylinders spin at high velocity, pulverizing and processing tons of material per second.",
            "s4_hud": "STEP 4: ELECTROMAGNETIC SEPARATION",
            "s4_desc": f"Electromagnetic guide channels and plasma scrubbers purge all impurities from the dense harvest stream.",
            "s5_hud": "STEP 5: VAULT COMPRESSION",
            "s5_desc": f"Giant hydraulic rams compact refined yield into high-density storage modules deep within the lower chassis.",
            "s68_desc": f"HUD text completely fades; camera descends rapidly past towering gantry struts into the belly factory, ending in a maximum close-up of electromagnetic guide coils suspending pure {clean_topic} streams, rhythm stabilizing into deep mechanical hum, no cuts, no scene transition, exactly 8 seconds."
        },
        {
            "level": 4,
            "name": "Level 4 - Autonomous Drone-Assisted Super-Harvester",
            "img_subj": f"A city-sized humanoid {clean_title} featuring twelve articulated harvesting arms, swarms of hundreds of autonomous harvesting drones, transparent processing domes, and multi-sensor crown.",
            "img_env": f"A vast multi-river delta transformed into an automated {clean_topic} super-complex, thousands of hectares visible, glowing dusk light reflecting on flooded plains.",
            "img_arch": f"Multi-deck mechanical torso containing visible automated factories, quantum-stabilized sorting towers, drone docking bays, and modular transit rails.",
            "img_eng": f"Brilliant cyan and amber energy conduits, electromagnetic levitation rails, localized thermal fields, and high-frequency sensor pulse rings.",
            "img_cin": f"Panoramic low-to-high vertical perspective, 9:16 framing, golden-hour volumetric lighting, photorealistic drone motion blur, deep cinematic atmosphere, 16K render.",
            "s1_hud": "STEP 1: DRONE FLEET SYNCHRONIZE",
            "s1_desc": f"Swarms of autonomous harvesting drones launch from the titan's chest bays in a glowing synchronized matrix.",
            "s2_hud": "STEP 2: COORDINATED EXTRACTION MATRIX",
            "s2_desc": f"Twelve primary arms and drone swarms sweep vast sectors simultaneously, channeling concentrated {clean_topic} rivers.",
            "s3_hud": "STEP 3: VACUUM INTAKE VORTEX",
            "s3_desc": f"Enormous aerodynamic vortex intakes swallow harvest streams directly into illuminated belly processing chambers.",
            "s4_hud": "STEP 4: MAGNETIC STRATIFICATION",
            "s4_desc": f"Multi-layered magnetic fields sort particles by density and purity at near-supersonic transit speeds.",
            "s5_hud": "STEP 5: AUTOMATED DRONE CARGO DOCK",
            "s5_desc": f"Purified materials are containerized and loaded into automated transit pods within internal distribution hubs.",
            "s68_desc": f"HUD text completely fades; camera flies smoothly alongside an incoming harvest stream into the transparent processing core, locking onto a single floating {clean_topic} grain passing through an energy sorter, mechanics stabilizing into flawless fluid motion, no cuts, no scene transition, exactly 8 seconds."
        },
        {
            "level": 5,
            "name": "Level 5 - Planetary Terraforming Harvester Colossus",
            "img_subj": f"A province-scale {clean_title} colossus towering into the lower stratosphere, twenty-four articulated robotic harvesting booms, planetary atmospheric processors, and monumental walking pylons.",
            "img_env": f"An entire planetary biome stretching to the curved horizon, cloud banks swirling around the titan's midsection, endless illuminated {clean_topic} basins below.",
            "img_arch": f"Vertically stacked orbital-grade processing cathedral, anti-matter containment pods, quantum-gravity separators, and subterranean intake anchors.",
            "img_eng": f"Quantum-blue energy halos, localized artificial gravity fields, plasma thermal loops, and visible gravitational lensing around primary intake collectors.",
            "img_cin": f"Epic sci-fi macro perspective, 9:16 vertical format, sunrise breaking above clouds, atmospheric ray dispersion, photorealistic planetary scale, 16K render.",
            "s1_hud": "STEP 1: QUANTUM SCAN MATRIX",
            "s1_desc": f"Planetary sensor arrays sweep the entire basin, mapping billions of {clean_topic} harvest coordinates in real-time.",
            "s2_hud": "STEP 2: CONTINENTAL MASS EXTRACTION",
            "s2_desc": f"Twenty-four harvesting booms engage, creating vast coordinated energy sweeps across hundreds of square kilometers.",
            "s3_hud": "STEP 3: GRAVITY-ASSISTED THRESH",
            "s3_desc": f"Harvest streams are drawn upward into the colossal torso via focused artificial gravity corridors.",
            "s4_hud": "STEP 4: PLASMA PURIFICATION",
            "s4_desc": f"High-energy plasma fields vaporize organic impurities while pristine {clean_topic} matter remains perfectly suspended.",
            "s5_hud": "STEP 5: COMPACTED CORE STORAGE",
            "s5_desc": f"Dense quantum compression fields pack hundreds of tons of refined harvest into glowing crystalline storage modules.",
            "s68_desc": f"HUD text completely fades; camera dives continuously through swirling cloud layers into the colossal gravity intake, terminating in an extreme close-up of a gravity-levitated {clean_topic} cluster shimmering in cyan energy, continuous planetary harvest stabilizing, no cuts, no scene transition, exactly 8 seconds."
        },
        {
            "level": 6,
            "name": "Level 6 - Biomechanical Geothermal Synthesis Titan",
            "img_subj": f"A sub-orbital scale biomechanical {clean_title} fusing crystalline exoskeleton armor with organic conduits, tectonic harvesting tendrils, and massive geothermal energy siphons.",
            "img_env": f"A volatile tectonic landscape rich in {clean_topic}, glowing fissures, volcanic steam columns, and orbital auroras dancing across the upper atmosphere.",
            "img_arch": f"Living biomechanical processing organs, crystalline filtration conduits, geothermal magma heat-exchangers, and bio-synthetic storage hives.",
            "img_eng": f"Molten golden-amber bio-luminescence, geothermal plasma discharge arcs, superconducting electromagnetic veins, and tectonic stabilization pulses.",
            "img_cin": f"Dramatic vertical cinematic framing (9:16), incandescent lava and auroral lighting, hyper-realistic crystalline textures, volumetric smoke, 16K render.",
            "s1_hud": "STEP 1: AWAKEN BIOMECHANICAL CORE",
            "s1_desc": f"Crystalline exoskeleton pulses with molten bio-energy as geothermal reactors sync across {clean_title}.",
            "s2_hud": "STEP 2: TECTONIC ROOT HARVEST",
            "s2_desc": f"Colossal biomechanical tendrils drill deep into the terrain, harvesting subterranean {clean_topic} veins at massive scale.",
            "s3_hud": "STEP 3: GEOTHERMAL CRACKING",
            "s3_desc": f"Superheated geothermal plasma streams break down raw harvested matter into pure organic components inside living chambers.",
            "s4_hud": "STEP 4: CRYSTALLINE FILTRATION",
            "s4_desc": f"Molecular crystalline lattices filter and align {clean_topic} structures with zero loss or thermal degradation.",
            "s5_hud": "STEP 5: BIO-HIVE ENCAPSULATION",
            "s5_desc": f"Refined yield is encapsulated into self-preserving bio-crystalline pods and stored in glowing hexagonal chamber walls.",
            "s68_desc": f"HUD text completely fades; camera plunges seamlessly into a glowing bio-conduit, reaching a maximum close-up of a crystalline cell enclosing a radiant {clean_topic} particle as surrounding tendrils pulse with steady bio-mechanical rhythm, no cuts, no scene transition, exactly 8 seconds."
        },
        {
            "level": 7,
            "name": "Level 7 - Atmospheric Sky-Spanning Ion Harvester",
            "img_subj": f"A sky-spanning floating {clean_title} held aloft by ionic repulsor engines and orbital tethers, sweeping planetary atmospheres with kilometer-wide energy scoops.",
            "img_env": f"Upper troposphere above vast {clean_topic} ecosystems, cloud oceans rolling below, setting sun blazing across the planetary limb.",
            "img_arch": f"Floating aerodynamic cathedral architecture, ionic particle separators, stratospheric intake turbines, orbital cargo launch catapults.",
            "img_eng": f"Intense violet and cyan ion beams, atmospheric ionization halos, anti-gravitational repulsor rings, and sonic shockwave rings.",
            "img_cin": f"Extreme high-altitude IMAX perspective, 9:16 vertical format, radiant sunset backlight, atmospheric refraction, 16K photorealistic render.",
            "s1_hud": "STEP 1: IONIC FIELD ENGAGE",
            "s1_desc": f"Atmospheric repulsor arrays activate, stabilizing the floating {clean_title} megastructure across upper cloud layers.",
            "s2_hud": "STEP 2: STRATOSPHERIC SWEEP",
            "s2_desc": f"Kilometer-wide ion scoops extend downward, vacuuming vast updrafts of airborne and surface {clean_topic} matter.",
            "s3_hud": "STEP 3: TURBO-CYCLONE REFINERY",
            "s3_desc": f"Stratospheric intake turbines compress and accelerate harvest streams through glowing spiral refinery ducts.",
            "s4_hud": "STEP 4: MOLECULAR ION PURIFICATION",
            "s4_desc": f"Focused ion lasers disintegrate atmospheric particulate, isolating pure molecular {clean_topic} yield.",
            "s5_hud": "STEP 5: ORBITAL CONTAINER LAUNCH",
            "s5_desc": f"Pressurized atmospheric containers fill and align on magnetic catapult tracks for orbital transfer.",
            "s68_desc": f"HUD text completely fades; camera glides alongside an ion beam straight into the central intake vortex, stopping at an ultra-macro view of a suspended {clean_topic} droplet glowing in violet ionization, engine hum stabilizing into continuous drone, no cuts, no scene transition, exactly 8 seconds."
        },
        {
            "level": 8,
            "name": "Level 8 - Dyson-Scale Stellar Resource Harvester",
            "img_subj": f"A Dyson-class stellar megastructure {clean_title} enveloping orbital space, solar plasma tap lines, tachyon sensor rings, and kilometer-long harvesting array sails.",
            "img_env": f"Deep space orbit above a planetary system, star flares erupting in the background, planet curve reflecting golden stellar light below.",
            "img_arch": f"Geometric hyper-alloy megatrusses, star-facing solar collectors, sub-atomic particle accelerators, hyper-space storage vaults.",
            "img_eng": f"Stellar plasma arcs, tachyon emission rings, space-time warping conduits, magnetic containment fields glowing brilliant gold and emerald.",
            "img_cin": f"Astronomical deep-space cinematography, 9:16 vertical composition, solar flare lens flare, photorealistic cosmic depth, 16K render.",
            "s1_hud": "STEP 1: STELLAR CONDUIT ALIGN",
            "s1_desc": f"Solar energy siphons lock onto stellar flare coordinates, fueling the massive planetary {clean_title} array.",
            "s2_hud": "STEP 2: ORBITAL HARVEST SWEEP",
            "s2_desc": f"Tachyon harvesting sails capture entire planetary resource streams of {clean_topic} across orbital trajectories.",
            "s3_hud": "STEP 3: SUB-ATOMIC FISSION THRESH",
            "s3_desc": f"Harvest streams undergo sub-atomic separation inside stellar containment rings at near-lightspeed velocity.",
            "s4_hud": "STEP 4: TACHYON PURIFICATION",
            "s4_desc": f"Tachyon radiation sweeps purge isotopic instability, rendering {clean_topic} output permanently indestructible.",
            "s5_hud": "STEP 5: HYPER-SPACE VAULT EXPANSION",
            "s5_desc": f"Pure yield materializes into dimensional storage manifolds capable of holding planetary reserves.",
            "s68_desc": f"HUD text completely fades; camera performs continuous descent through space into the stellar core collector, ending in a maximum close-up of a tachyon-stabilized {clean_topic} grain floating beside glowing containment coils, mechanics stabilizing into cosmic harmony, no cuts, no scene transition, exactly 8 seconds."
        },
        {
            "level": 9,
            "name": "Level 9 - Transdimensional Singularity Harvester",
            "img_subj": f"A transdimensional reality-warping {clean_title} entity whose geometry fractures across multiple dimensions, featuring quantum singularity intake engines and non-Euclidean harvesting tendrils.",
            "img_env": f"Fractured space-time horizon above {clean_topic} worlds, multiple overlapping dimensions visible simultaneously, quantum nebula clouds.",
            "img_arch": f"Impossible non-Euclidean geometry, floating hyper-dimensional rings, event-horizon extraction chambers, temporal containment silos.",
            "img_eng": f"Gravitational lensing waves, dark energy aura, temporal distortion waves, radiant ultraviolet quantum discharge arcs.",
            "img_cin": f"Mind-bending surreal sci-fi aesthetic, 9:16 vertical format, cosmic scale lighting, chromatic aberration, photorealistic dimensional textures, 16K render.",
            "s1_hud": "STEP 1: FOLD LOCAL DIMENSIONS",
            "s1_desc": f"Spacetime metrics bend as the quantum singularity engine awakens inside {clean_title}.",
            "s2_hud": "STEP 2: MULTI-REALITY HARVEST",
            "s2_desc": f"Transdimensional tendrils reach across parallel timelines, gathering infinite variants of {clean_topic} simultaneously.",
            "s3_hud": "STEP 3: SINGULARITY THRESHING FACTORY",
            "s3_desc": f"Crop streams enter micro-black-hole event horizons, separating pure matter from entropy.",
            "s4_hud": "STEP 4: QUANTUM ENTANGLEMENT PURIFY",
            "s4_desc": f"Entangled field pulses harmonize the harvested atoms into flawless atomic resonance.",
            "s5_hud": "STEP 5: TEMPORAL VAULT LOCK",
            "s5_desc": f"Infinitely dense harvest stores freeze into temporal stasis chambers, preserved for eternity.",
            "s68_desc": f"HUD text completely fades; camera descends through fractured spatial planes into the singularity core, halting in an extreme close-up of a timeless {clean_topic} particle hovering within a glowing event horizon ring, eternal harvesting cycle stabilizing, no cuts, no scene transition, exactly 8 seconds."
        },
        {
            "level": 10,
            "name": "Level 10 - ALIEN LEVEL / MAXIMUM",
            "img_subj": f"The ultimate god-tier alien {clean_title} megastructure, a transcendent cosmic intelligence commanding planetary-scale sensor halos, transdimensional harvesting arms reaching through folded reality, and an infinite-dimensional processing heart.",
            "img_env": f"Multiple worlds and cosmic horizons converging beneath the titan's presence, billions of hectares of {clean_topic} across infinite realities illuminated in ethereal cosmic dawn light.",
            "img_arch": f"Alien hyper-matter chassis, transparent hyper-dimensional processing cathedrals, wormhole intake conduits, infinite-dimensional storage spheres glowing with limitless yield.",
            "img_eng": f"Ethereal multi-spectrum cosmic radiance, dimensional gravity waves, tachyon quantum loops, and reality-stabilizing field geometries.",
            "img_cin": f"Supreme cinematic masterpiece, 9:16 vertical framing, IMAX cosmic angle, photorealistic hyper-detailed alien textures, breathtaking lighting and reflections, 16K render.",
            "s1_hud": "STEP 1: AWAKEN THE TITAN",
            "s1_desc": f"The alien agricultural intelligence activates, illuminating countless sensor halos and planetary-scale harvesting systems across {clean_title}.",
            "s2_hud": "STEP 2: HARVEST REALITY",
            "s2_desc": f"Innumerable colossal arms reach through folded space and gather {clean_topic} from multiple worlds simultaneously.",
            "s3_hud": "STEP 3: TRANSDIMENSIONAL THRESH",
            "s3_desc": f"Entire crop streams enter wormholes and emerge inside the titan's impossible belly factory.",
            "s4_hud": "STEP 4: QUANTUM PURIFICATION",
            "s4_desc": f"Individual {clean_topic} particles float through miniature artificial suns, gravitational separators, magnetic fields, and alien drying reactors.",
            "s5_hud": "STEP 5: STORE THE HARVEST UNIVERSE",
            "s5_desc": f"Finished yield cascades into an infinite-dimensional storage chamber containing vast glowing reserves of {clean_topic}.",
            "s68_desc": f"HUD text completely fades; the camera performs a continuous impossible-scale descent from the cosmic titan into its belly, through alien processing architecture, and finally reaches a maximum close-up of a single {clean_topic} grain suspended beside a colossal quantum mechanism, with the surrounding machinery stabilizing into a mesmerizing continuous harvesting rhythm, no cuts, no scene transition, exactly 8 seconds."
        }
    ]

    results = []
    for t in tiers:
        lvl = t["level"]
        img_text = f"""5-Layer Open Montage Structure

Layer 1 — Subject: {t['img_subj']}

Layer 2 — Environment: {t['img_env']}

Layer 3 — Architecture: {t['img_arch']}

Layer 4 — Energy/Physics: {t['img_eng']}

Layer 5 — Cinematic Presentation: {t['img_cin']}"""

        vid_text = f"""Exactly 8 seconds, 9:16 vertical aspect ratio, photorealistic cinematic render, smooth continuous motion, no cuts, maximum cinematic realism.

Second 1 [0:00-0:01] — HUD Popup Text: "{t['s1_hud']}" — {t['s1_desc']}

Second 2 [0:01-0:02] — HUD Popup Text: "{t['s2_hud']}" — {t['s2_desc']}

Second 3 [0:02-0:03] — HUD Popup Text: "{t['s3_hud']}" — {t['s3_desc']}

Second 4 [0:03-0:04] — HUD Popup Text: "{t['s4_hud']}" — {t['s4_desc']}

Second 5 [0:04-0:05] — HUD Popup Text: "{t['s5_hud']}" — {t['s5_desc']}

Seconds 6-8 [0:05-0:08]: {t['s68_desc']}"""

        results.append({
            "level": lvl,
            "level_name": t["name"],
            "image_prompt": img_text,
            "video_prompt": vid_text
        })

    return results


def extract_and_repair_levels_from_llm(output_text: str) -> list[dict]:
    """Robust multi-pass parser to extract 10 levels from LLM output even with unescaped internal quotes or markdown formatting."""
    if not output_text or not output_text.strip():
        return []

    # Clean markdown codeblocks
    clean_text = re.sub(r'^```(?:json)?\s*', '', output_text.strip(), flags=re.MULTILINE)
    clean_text = re.sub(r'```$', '', clean_text.strip(), flags=re.MULTILINE)

    # Pass 1: Standard JSON array extraction
    match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', clean_text)
    if match:
        try:
            items = json.loads(match.group(0))
            if isinstance(items, list) and len(items) >= 5:
                results = {}
                for idx, it in enumerate(items, 1):
                    lvl = it.get("level", idx)
                    name = it.get("level_name", f"Level {lvl}")
                    img = str(it.get("image_prompt", "")).strip()
                    vid = str(it.get("video_prompt", "")).strip()
                    if img and vid and 1 <= lvl <= 10 and lvl not in results:
                        results[lvl] = {"level": lvl, "level_name": name, "image_prompt": img, "video_prompt": vid}
                if len(results) >= 10:
                    return [results[k] for k in sorted(results.keys())[:10]]
        except Exception:
            pass

    # Pass 2: Delimiter-based splitting by "level": X (Handles unescaped quotes inside image/video prompt strings)
    level_chunks = re.split(r'(?:\{|\n)\s*\"?level\"?\s*:\s*(\d+)', output_text)
    if len(level_chunks) >= 5:
        levels = {}
        for i in range(1, len(level_chunks), 2):
            try:
                lvl = int(level_chunks[i].strip())
                chunk = level_chunks[i+1]

                name_m = re.search(r'\"?level_name\"?\s*:\s*\"([^\"]+)\"', chunk)
                name = name_m.group(1) if name_m else f"Level {lvl}"

                img_m = re.search(r'\"?image_prompt\"?\s*:\s*\"([\s\S]*?)(?=\"\s*,\s*\"?video_prompt\"?)', chunk)
                img = img_m.group(1) if img_m else ""

                vid_m = re.search(r'\"?video_prompt\"?\s*:\s*\"([\s\S]*?)(?=\"\s*\}\s*,|\"\s*\}\s*\]|\"\s*\}\s*$|\Z)', chunk)
                vid = vid_m.group(1) if vid_m else ""

                img = img.replace('\\n', '\n').replace('\\"', '"').strip()
                vid = vid.replace('\\n', '\n').replace('\\"', '"').strip()

                if 1 <= lvl <= 10 and lvl not in levels and img and vid:
                    levels[lvl] = {"level": lvl, "level_name": name, "image_prompt": img, "video_prompt": vid}
            except Exception:
                continue

        if len(levels) >= 10:
            return [levels[k] for k in sorted(levels.keys())[:10]]

    # Pass 3: Text format fallback (e.g. LEVEL 1 ... IMAGE ... VIDEO ...)
    level_blocks = re.split(r'LEVEL\s+(\d+)\s*[\—\-–:]\s*([^\n]+)', output_text, flags=re.IGNORECASE)
    if len(level_blocks) >= 4:
        text_levels = {}
        for i in range(1, len(level_blocks), 3):
            lvl_num = int(level_blocks[i].strip())
            lvl_name = f"Level {lvl_num} - {level_blocks[i+1].strip()}"
            block = level_blocks[i+2]
            img_match = re.search(r'IMAGE\s*\d*\s*[:\-]\s*(.*?)(?=VIDEO|\Z)', block, re.DOTALL | re.IGNORECASE)
            vid_match = re.search(r'VIDEO\s*\d*\s*[:\-]\s*(.*?)(?=LEVEL|\Z)', block, re.DOTALL | re.IGNORECASE)
            img_text = img_match.group(1).strip() if img_match else ""
            vid_text = vid_match.group(1).strip() if vid_match else ""
            if img_text and vid_text and 1 <= lvl_num <= 10 and lvl_num not in text_levels:
                text_levels[lvl_num] = {
                    "level": lvl_num,
                    "level_name": lvl_name,
                    "image_prompt": img_text,
                    "video_prompt": vid_text
                }
        if len(text_levels) >= 10:
            return [text_levels[k] for k in sorted(text_levels.keys())[:10]]

    return []


def generate_escalation_for_idea(idea: Idea, skip_browser: bool = False) -> list[Prompt]:
    """Level 3 -> Level 4: Generates 10 Image + 10 Video Prompts (Level 1 to 10) for an Idea."""
    init_db()
    print(f"\n[Hierarchy Step 3 -> 4] Generating 10-Level Escalation Prompts for Idea #{idea.id}: '{idea.title}' (Topic: {idea.topic})...")

    style = get_prompt_style("STAGE_3_PROMPT_ESCALATION_MASTER")
    if style:
        prompt_instruction = style.prompt_template.format(
            idea_title=idea.title,
            topic=idea.topic or 'General',
            description=idea.description or idea.raw_idea
        )
    else:
        prompt_instruction = f"Given {idea.title}, build 10-level escalation (10 image + 10 video prompts in 9:16 ratio)."

    output_text = ""
    if not skip_browser:
        try:
            output_text = call_chatgpt_playwright(prompt_instruction, wait_seconds=300)
        except Exception as e:
            print(f"[Notice] CloakBrowser prompt escalation notice: {e}")

    parsed_levels = extract_and_repair_levels_from_llm(output_text)

    # Handle incomplete or failed generation
    if len(parsed_levels) < 10:
        if not skip_browser:
            print(f"[Error] ChatGPT did not return complete 10 levels for Idea #{idea.id} ('{idea.title}'). Keeping idea unfilled for live LLM generation.")
            return []
        else:
            # Offline test mode only when --skip-browser is explicitly passed
            parsed_levels = build_rich_escalation_system(idea.title, idea.topic or "", idea.description or "")

    saved_prompts = []
    with get_session() as session:
        old_prompts = session.exec(select(Prompt).where(Prompt.idea_id == idea.id)).all()
        for op in old_prompts:
            session.delete(op)
        session.commit()

        for item in parsed_levels:
            lvl = item["level"]
            lvl_name = item["level_name"]
            
            img_prompt = Prompt(
                uuid=str(uuid.uuid4()),
                idea_id=idea.id,
                prompt_type="image_prompt",
                title=f"{idea.title} - {lvl_name} (Image)",
                prompt_text=item["image_prompt"],
                generation_type="image",
                aspect_ratio="9:16",
                level=lvl,
                level_name=lvl_name,
                structure_type="5_layer_montage",
                status="ready"
            )
            session.add(img_prompt)
            session.commit()
            session.refresh(img_prompt)

            vid_prompt = Prompt(
                uuid=str(uuid.uuid4()),
                idea_id=idea.id,
                prompt_type="video_prompt",
                title=f"{idea.title} - {lvl_name} (Video 8s)",
                prompt_text=item["video_prompt"],
                generation_type="video",
                aspect_ratio="9:16",
                duration_seconds=8.0,
                level=lvl,
                level_name=lvl_name,
                structure_type="8s_5_step_hud_popup",
                reference_image_prompt_id=img_prompt.id,
                status="ready"
            )
            session.add(vid_prompt)
            session.commit()
            session.refresh(vid_prompt)
            saved_prompts.extend([img_prompt, vid_prompt])

    print(f"[Success] Inserted 20 prompts (10 Image + 10 Video in 9:16 vertical) for Idea #{idea.id} into `prompts` table!")
    return saved_prompts


# ============================================================================
# 3. BACKWARD DEPENDENCY RESOLUTION ENGINE
# ============================================================================

def is_idea_packaged_and_completed(idea_id: int) -> bool:
    init_db()
    with get_session() as session:
        idea = session.exec(select(Idea).where(Idea.id == idea_id)).first()
        if not idea:
            return False
        
        # Must actually have 20 prompts
        prompt_count = len(session.exec(select(Prompt).where(Prompt.idea_id == idea_id)).all())
        if prompt_count < 20:
            return False

        # Check for folder matching the idea
        clean_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', idea.title).strip('_')
        for folder in OUTPUT_DIR.glob(f"*{clean_title}*"):
            if folder.is_dir():
                real_mp4s = [f for f in folder.glob("*.mp4") if f.stat().st_size > 10240]
                has_meta = (folder / "youtube_metadata.json").exists() and (folder / "youtube_metadata.json").stat().st_size > 0
                has_prompt_info = (folder / "prompt_info.json").exists() and (folder / "prompt_info.json").stat().st_size > 0
                if real_mp4s and has_meta and has_prompt_info:
                    return True

        task = session.exec(select(Task).where(Task.idea_id == idea_id, Task.status == "success")).first()
        if task and task.output_folder_path:
            p = Path(task.output_folder_path)
            if p.exists():
                real_mp4s = [f for f in p.glob("*.mp4") if f.stat().st_size > 10240]
                has_meta = (p / "youtube_metadata.json").exists() and (p / "youtube_metadata.json").stat().st_size > 0
                has_prompt_info = (p / "prompt_info.json").exists() and (p / "prompt_info.json").stat().st_size > 0
                if real_mp4s and has_meta and has_prompt_info:
                    return True
    return False


def get_or_create_next_production_ready_prompt(skip_browser: bool = False, fill_unfilled_only: bool = False) -> dict:
    """
    Strict Sequential Element-by-Element Backward Dependency Resolution:
    Iterates through Elements in ascending order (Element 1 Paddy -> Element 2 Forest -> ... -> Element 100).
    For each Element:
      1. If Element has 0 ideas in SQLite -> Generates 10 Ideas -> Picks Idea 1 -> Generates 1-10 Prompts.
      2. If Element has Ideas -> Checks each Idea in ascending order:
         - If Idea has < 20 Prompts -> Generates 1-10 Escalation Prompts (10 Image + 10 Video) -> Returns Level 10 Prompt.
         - If Idea has 20 Prompts & fill_unfilled_only is False (Video Generation mode) -> Returns Level 10 Prompt for packaging.
         - If Idea has 20 Prompts & fill_unfilled_only is True (Fillup Loop mode) -> Advances to next Idea in Element!
      3. If all current Ideas of an Element have 20 prompts, but Element has < 10 Ideas total -> Generates remaining Ideas to reach 10!
      4. When all 10 Ideas of an Element are 100% completed with 20 prompts each, advances to the next Element.
      5. When all 100 Elements are completed, dynamically generates Element #101+ from Category.
    """
    init_db()
    print("=" * 70)
    print("BACKWARD DEPENDENCY CHAIN CHECK: SEQUENTIAL HIERARCHY (ELEMENTS 1 -> 100)")
    print("=" * 70)

    with get_session() as session:
        all_elements = session.exec(select(Element).order_by(Element.id.asc())).all()

        for elem in all_elements:
            # Find linked ideas for this element
            idea_links = session.exec(select(IdeaElement).where(IdeaElement.element_id == elem.id)).all()
            linked_idea_ids = [il.idea_id for il in idea_links]

            if not linked_idea_ids:
                # Element has NO ideas yet -> Generate 10 ideas for this element
                print(f"\n[Hierarchy: Element #{elem.id} '{elem.name}' has 0 Ideas -> Generating 10 Ideas...]")
                new_ideas = generate_ideas_for_element(elem, skip_browser=skip_browser)
                first_idea = new_ideas[0]
                generate_escalation_for_idea(first_idea, skip_browser=skip_browser)

                lvl10_vid = session.exec(select(Prompt).where(
                    Prompt.idea_id == first_idea.id,
                    Prompt.level == 10,
                    Prompt.generation_type == "video"
                )).first()
                lvl10_img = session.exec(select(Prompt).where(
                    Prompt.idea_id == first_idea.id,
                    Prompt.level == 10,
                    Prompt.generation_type == "image"
                )).first()

                return {
                    "status": "READY_FOR_VIDEO",
                    "idea_id": first_idea.id,
                    "idea_title": first_idea.title,
                    "idea_topic": first_idea.topic,
                    "level_10_video_prompt": lvl10_vid,
                    "level_10_image_prompt": lvl10_img,
                    "source_step": f"GENERATED_IDEAS_FOR_ELEMENT_{elem.id}_{elem.name}"
                }

            # Element has ideas -> Check each idea in order
            for idea_id in sorted(linked_idea_ids):
                idea = session.exec(select(Idea).where(Idea.id == idea_id)).first()
                if not idea:
                    continue

                if is_idea_packaged_and_completed(idea.id):
                    # Already 100% done and locked -> check next idea
                    continue

                prompts = session.exec(select(Prompt).where(Prompt.idea_id == idea.id)).all()
                prompt_count = len(prompts)

                lvl10_vid = session.exec(select(Prompt).where(
                    Prompt.idea_id == idea.id,
                    Prompt.level == 10,
                    Prompt.generation_type == "video"
                )).first()
                lvl10_img = session.exec(select(Prompt).where(
                    Prompt.idea_id == idea.id,
                    Prompt.level == 10,
                    Prompt.generation_type == "image"
                )).first()

                filled_prompts = [p for p in prompts if p.prompt_text and len(p.prompt_text.strip()) > 50]
                has_all_20_filled = len(filled_prompts) >= 20 and lvl10_vid and lvl10_vid.prompt_text and len(lvl10_vid.prompt_text.strip()) > 50

                # If idea already has 20 valid, filled prompts:
                if has_all_20_filled:
                    if not fill_unfilled_only:
                        # Video generation packaging mode: pick this ready idea
                        print(f"\n[Hierarchy: Found Ready Prompt for Element #{elem.id} '{elem.name}']")
                        print(f"  -> Idea #{idea.id}: '{idea.title}'")
                        print(f"  -> Level 10 Video Prompt #{lvl10_vid.id} is PRODUCTION-READY in `prompts` table!")
                        return {
                            "status": "READY_FOR_VIDEO",
                            "idea_id": idea.id,
                            "idea_title": idea.title,
                            "idea_topic": idea.topic,
                            "level_10_video_prompt": lvl10_vid,
                            "level_10_image_prompt": lvl10_img,
                            "source_step": f"EXISTING_PROMPT_ELEMENT_{elem.id}_{idea.title}"
                        }
                    else:
                        # In fill_unfilled_only loop mode, advance to check remaining ideas in this element!
                        continue

                # Idea has blank/missing prompts -> Generate 1-10 escalation prompts!
                print(f"\n[Hierarchy: Element #{elem.id} '{elem.name}' -> Idea #{idea.id} '{idea.title}' has {len(filled_prompts)}/20 filled prompts]")
                print(f"  -> Auto-generating 10-level escalation prompts (10 Image + 10 Video)...")
                generate_escalation_for_idea(idea, skip_browser=skip_browser)

                lvl10_vid = session.exec(select(Prompt).where(
                    Prompt.idea_id == idea.id,
                    Prompt.level == 10,
                    Prompt.generation_type == "video"
                )).first()
                lvl10_img = session.exec(select(Prompt).where(
                    Prompt.idea_id == idea.id,
                    Prompt.level == 10,
                    Prompt.generation_type == "image"
                )).first()

                return {
                    "status": "READY_FOR_VIDEO",
                    "idea_id": idea.id,
                    "idea_title": idea.title,
                    "idea_topic": idea.topic,
                    "level_10_video_prompt": lvl10_vid,
                    "level_10_image_prompt": lvl10_img,
                    "source_step": f"GENERATED_ESCALATION_FOR_IDEA_{idea.id}_{idea.title}"
                }

            # If all existing ideas for this element are done, but it has < 10 ideas total -> Generate remaining ideas!
            if len(linked_idea_ids) < 10:
                print(f"\n[Hierarchy: Element #{elem.id} '{elem.name}' has only {len(linked_idea_ids)}/10 Ideas -> Generating more to reach 10 ideas...]")
                new_ideas = generate_ideas_for_element(elem, skip_browser=skip_browser)
                first_idea = new_ideas[0]
                generate_escalation_for_idea(first_idea, skip_browser=skip_browser)

                lvl10_vid = session.exec(select(Prompt).where(
                    Prompt.idea_id == first_idea.id,
                    Prompt.level == 10,
                    Prompt.generation_type == "video"
                )).first()
                lvl10_img = session.exec(select(Prompt).where(
                    Prompt.idea_id == first_idea.id,
                    Prompt.level == 10,
                    Prompt.generation_type == "image"
                )).first()

                return {
                    "status": "READY_FOR_VIDEO",
                    "idea_id": first_idea.id,
                    "idea_title": first_idea.title,
                    "idea_topic": first_idea.topic,
                    "level_10_video_prompt": lvl10_vid,
                    "level_10_image_prompt": lvl10_img,
                    "source_step": f"TOPPED_UP_IDEAS_FOR_ELEMENT_{elem.id}_{elem.name}"
                }

    # If all 100 Elements are completed -> Generate Element #101 from Category
    print(f"\n[Hierarchy: All 100 Elements Completed -> Generating Brand New Element #101+]")
    with get_session() as session:
        cat = session.exec(select(Category)).first()
        cat_name = cat.name if cat else "Impossible Giant Machine"

    new_element = generate_new_element_from_category(cat_name, skip_browser=skip_browser)
    new_ideas = generate_ideas_for_element(new_element, skip_browser=skip_browser)
    first_idea = new_ideas[0]
    generate_escalation_for_idea(first_idea, skip_browser=skip_browser)

    with get_session() as session:
        lvl10_vid = session.exec(select(Prompt).where(
            Prompt.idea_id == first_idea.id,
            Prompt.level == 10,
            Prompt.generation_type == "video"
        )).first()
        lvl10_img = session.exec(select(Prompt).where(
            Prompt.idea_id == first_idea.id,
            Prompt.level == 10,
            Prompt.generation_type == "image"
        )).first()

    return {
        "status": "READY_FOR_VIDEO",
        "idea_id": first_idea.id,
        "idea_title": first_idea.title,
        "idea_topic": first_idea.topic,
        "level_10_video_prompt": lvl10_vid,
        "level_10_image_prompt": lvl10_img,
        "source_step": f"GENERATED_NEW_ELEMENT_{new_element.id}"
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backward Dependency Prompt Chain Engine")
    parser.add_argument("--skip-browser", action="store_true", help="Skip live browser launch and test resolution logic")
    args = parser.parse_args()

    result = get_or_create_next_production_ready_prompt(skip_browser=args.skip_browser)
    print("\n" + "=" * 70)
    print("PRODUCTION-READY PROMPT RESOLVED SUCCESSFULLY:")
    print("=" * 70)
    print(f"Idea ID:              {result['idea_id']}")
    print(f"Idea Title:           {result['idea_title']}")
    print(f"Topic:                {result['idea_topic']}")
    print(f"Source Chain Step:    {result['source_step']}")
    print(f"Level 10 Video Title: {result['level_10_video_prompt'].title}")
    print(f"Level 10 Video Text:  {result['level_10_video_prompt'].prompt_text[:150]}...")
    print("=" * 70 + "\n")
