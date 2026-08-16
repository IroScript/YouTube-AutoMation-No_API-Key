"""
Prompt Fillup Runner - Part 1: Autonomous Hierarchical Prompt Generator (Clean)
================================================================================
Runs the backward dependency checking loop to resolve and fill all blank tables
for the next idea in the pipeline:
  categories -> elements -> ideas -> 10-level prompts -> Level 10 Production Ready!

Usage:
  python run_prompt_fillup.py                   (Live Playwright ChatGPT generation)
  python run_prompt_fillup.py --skip-browser    (Instant dry-run / fast structure generation)
  python run_prompt_fillup.py --continuous      (Continuously fill prompts for all ideas in a loop)
"""

import sys
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from prompt_chain_engine import get_or_create_next_production_ready_prompt
from database.session import init_db, get_session
from database.models import Element, Idea, Prompt


def run_single_fillup(skip_browser: bool = False):
    """Executes exactly one prompt fillup cycle for the next idea."""
    print("\n" + "#" * 75)
    print("▶ [PART 1: PROMPT FILLUP ENGINE] Starting Autonomous Resolution...")
    print("#" * 75)

    result = get_or_create_next_production_ready_prompt(skip_browser=skip_browser)

    print("\n" + "=" * 75)
    print("✅ [FILLUP COMPLETE] NEXT PRODUCTION-READY PROMPT IS READY FOR VIDEO GENERATION:")
    print("=" * 75)
    print(f"  • Idea ID:              #{result['idea_id']}")
    print(f"  • Idea Title:           {result['idea_title']}")
    print(f"  • Element/Topic:        {result['idea_topic']}")
    print(f"  • Dependency Resolved:  {result['source_step']}")
    print(f"  • Level 10 Video Title: {result['level_10_video_prompt'].title}")
    print(f"  • Level 10 Video Text:  {result['level_10_video_prompt'].prompt_text[:120]}...")
    print("=" * 75 + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description="Prompt Fillup Engine Runner")
    parser.add_argument("--skip-browser", action="store_true", help="Skip browser automation and generate structure directly for testing")
    parser.add_argument("--continuous", action="store_true", help="Run in continuous loop filling prompts for multiple ideas")
    parser.add_argument("--count", type=int, default=1, help="Number of idea prompt cycles to run")
    args = parser.parse_args()

    init_db()

    iterations = args.count if not args.continuous else 999999
    for i in range(1, iterations + 1):
        if iterations > 1:
            print(f"\n>>> Running Cycle {i}/{iterations}...")
        res = run_single_fillup(skip_browser=args.skip_browser)
        if not args.continuous and i == iterations:
            break


if __name__ == "__main__":
    main()
