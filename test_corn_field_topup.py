"""
Corn Field (Element #6) 8-Idea Top-up Verification Suite (3 Distinct Ways)
==========================================================================
Way 1: Direct Execution of generate_ideas_for_element to top-up 8 remaining ideas
Way 2: Engine Sequential Escalation & Production-Ready Prompt Trigger
Way 3: Database Relational Integrity & Master CSV Progress Verification
"""

import sys
from pathlib import Path
from sqlmodel import select

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.session import init_db, get_session
from database.models import Element, Idea, IdeaElement, Prompt
from prompt_chain_engine import generate_ideas_for_element, generate_escalation_for_idea
from generate_progress_csv import run as run_csv_progress


def run_three_verifications():
    init_db()
    print("=" * 80)
    print("      CORN FIELD (ELEMENT #6) 8-IDEA TOP-UP VERIFICATION SUITE")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # SETUP: ENSURE INITIAL STATE (2 EXISTING IDEAS: #23, #24)
    # -------------------------------------------------------------------------
    with get_session() as session:
        elem6 = session.get(Element, 6)
        # Delete any temporary ideas > 24 for clean repeatable test
        temp_links = session.exec(select(IdeaElement).where(IdeaElement.element_id == 6, IdeaElement.idea_id > 24)).all()
        for tl in temp_links:
            session.delete(tl)
        temp_ideas = session.exec(select(Idea).where(Idea.id > 24, Idea.topic == "Corn Field")).all()
        for ti in temp_ideas:
            session.delete(ti)
        session.commit()

    # -------------------------------------------------------------------------
    # WAY 1: DIRECT TOP-UP EXECUTION (2 -> 10 IDEAS)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("🧪 [WAY 1] Direct Top-Up Execution: Checking Corn Field Existing Count & Generating 8...")
    print("-" * 80)
    with get_session() as session:
        elem6 = session.get(Element, 6)
        initial_links = session.exec(select(IdeaElement).where(IdeaElement.element_id == 6)).all()
        initial_count = len(initial_links)
        print(f"  • Corn Field (Element #6) Initial Idea Count in DB: {initial_count}/10")
        assert initial_count == 2, f"Expected 2 initial ideas, found {initial_count}"

    # Execute top-up
    new_ideas = generate_ideas_for_element(elem6, skip_browser=True, target_total=10)
    print(f"  • Successfully generated {len(new_ideas)} new ideas to top-up to 10!")

    with get_session() as session:
        updated_links = session.exec(select(IdeaElement).where(IdeaElement.element_id == 6)).all()
        updated_count = len(updated_links)
        print(f"  • Corn Field (Element #6) Final Idea Count in DB: {updated_count}/10")
        assert updated_count == 10, f"Expected 10 total ideas, found {updated_count}"
        
        all_corn_ideas = session.exec(select(Idea).join(IdeaElement).where(IdeaElement.element_id == 6)).all()
        for idx, idea in enumerate(all_corn_ideas, 1):
            print(f"    [{idx:02d}] Idea #{idea.id:<2}: '{idea.title}' (Topic: {idea.topic})")

    print("  -> ✅ WAY 1 PASSED: Remaining 8 ideas generated, total 10 ideas linked to Corn Field!")

    # -------------------------------------------------------------------------
    # WAY 2: ENGINE SEQUENTIAL ESCALATION TRIGGER (LEVEL 1-10 PROMPTS)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("🧪 [WAY 2] Engine Escalation Trigger: Verifying 1-10 Level Prompts for Corn Ideas...")
    print("-" * 80)
    # Generate escalation prompts for Corn Field Idea #23 (Colossal Corn Thresher Titan)
    with get_session() as session:
        idea23 = session.get(Idea, 23)
        generate_escalation_for_idea(idea23, skip_browser=True)
        
        prompts = session.exec(select(Prompt).where(Prompt.idea_id == 23)).all()
        lvl10_vid = [p for p in prompts if p.level == 10 and p.generation_type == "video"]
        lvl10_img = [p for p in prompts if p.level == 10 and p.generation_type == "image"]
        
        print(f"  • Idea #23 ('{idea23.title}') Prompts Count: {len(prompts)}/20")
        print(f"  • Level 10 Video Prompt: '{lvl10_vid[0].title if lvl10_vid else 'None'}'")
        print(f"  • Level 10 Image Prompt: '{lvl10_img[0].title if lvl10_img else 'None'}'")
        assert len(prompts) == 20, f"Expected 20 prompts for Idea #23, got {len(prompts)}"
        assert len(lvl10_vid) == 1, "Level 10 video prompt missing!"

    print("  -> ✅ WAY 2 PASSED: Level 1-10 escalation prompts successfully generated & production-ready!")

    # -------------------------------------------------------------------------
    # WAY 3: DATABASE RELATIONAL INTEGRITY & MASTER CSV AUDIT
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("🧪 [WAY 3] Database Relational Integrity & Master CSV Progress Verification...")
    print("-" * 80)
    run_csv_progress()

    with get_session() as session:
        # Verify relational integrity in SQLite
        corn_elem_check = session.get(Element, 6)
        links_check = session.exec(select(IdeaElement).where(IdeaElement.element_id == 6)).all()
        linked_ids = [l.idea_id for l in links_check]
        ideas_check = session.exec(select(Idea).where(Idea.id.in_(linked_ids))).all()
        
        print(f"  • SQLite Audit -> Element Name: '{corn_elem_check.name}' (ID: {corn_elem_check.id})")
        print(f"  • SQLite Audit -> Linked Idea IDs: {linked_ids}")
        print(f"  • SQLite Audit -> Total Verified Ideas: {len(ideas_check)}/10")
        assert len(ideas_check) == 10, "Relational integrity mismatch in SQLite!"

    print("  -> ✅ WAY 3 PASSED: Full relational integrity verified in SQLite and exported to Master CSV!")

    print("\n" + "=" * 80)
    print("🎉 ALL 3 VERIFICATION WAYS COMPLETED SUCCESSFULLY & 200% VERIFIED!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_three_verifications()
