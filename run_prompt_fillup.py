"""
Prompt Fillup Runner - Part 1: Autonomous Hierarchical Prompt Generator (Loop & Live Monitoring)
================================================================================================
Runs the backward dependency checking loop to resolve and fill all blank tables
for the next idea in the pipeline:
  categories -> elements -> ideas -> 10-level prompts -> Level 10 Production Ready!

Usage:
  python run_prompt_fillup.py                   (Run continuous loop by default)
  python run_prompt_fillup.py --count 5         (Run exactly 5 fillup cycles)
  python run_prompt_fillup.py --skip-browser    (Instant dry-run / fast test structure)
"""

import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from prompt_chain_engine import get_or_create_next_production_ready_prompt
from database.session import init_db, get_session
from database.models import Element, Idea, Prompt, Task
from generate_progress_csv import generate_pipeline_hierarchy_progress, generate_table_fillup_summary, export_raw_tables, DB_PATH, CSV_TABLES_DIR
from generate_master_joined_csv import generate_unified_master_csv


def get_current_pipeline_stats():
    """Returns quick count of elements, ideas, and prompts in SQLite."""
    init_db()
    with get_session() as session:
        from sqlmodel import select
        elem_count = len(session.exec(select(Element)).all())
        idea_count = len(session.exec(select(Idea)).all())
        prompt_count = len(session.exec(select(Prompt)).all())
        task_count = len(session.exec(select(Task)).all())
    return {
        "elements": elem_count,
        "ideas": idea_count,
        "prompts": prompt_count,
        "tasks": task_count
    }


def run_single_fillup(skip_browser: bool = False, cycle_num: int = 1):
    """Executes exactly one prompt fillup cycle for the next idea."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "#" * 80)
    print(f"▶ [CYCLE #{cycle_num} | {now_str}] PROMPT FILLUP ENGINE: Resolving Next Dependency...")
    print("#" * 80)

    result = get_or_create_next_production_ready_prompt(skip_browser=skip_browser, fill_unfilled_only=True)

    if result and result.get('level_10_video_prompt'):
        print("\n" + "=" * 80)
        print(f"✅ [CYCLE #{cycle_num} COMPLETE] PRODUCTION-READY PROMPT GENERATED & SAVED:")
        print("=" * 80)
        print(f"  • Idea ID:              #{result['idea_id']}")
        print(f"  • Idea Title:           {result['idea_title']}")
        print(f"  • Element/Topic:        {result['idea_topic']}")
        print(f"  • Dependency Resolved:  {result['source_step']}")
        print(f"  • Level 10 Video Title: {result['level_10_video_prompt'].title}")
        print(f"  • Level 10 Video Text:  {result['level_10_video_prompt'].prompt_text[:120]}...")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print(f"⏳ [CYCLE #{cycle_num}] LLM Response Pending / Retrying next cycle...")
        print("=" * 80)

    # Sync CSV exports in real-time
    try:
        print("[Auto-Sync] Refreshing progress and unified master CSV exports...")
        table_summaries = export_raw_tables(DB_PATH, CSV_TABLES_DIR)
        generate_table_fillup_summary(table_summaries)
        generate_pipeline_hierarchy_progress()
        generate_unified_master_csv()
        print("[Auto-Sync] All CSV exports updated successfully.")
    except Exception as e:
        print(f"[Auto-Sync Notice] CSV export notice: {e}")

    stats = get_current_pipeline_stats()
    print(f"📊 [DATABASE TOTALS] Elements: {stats['elements']} | Ideas: {stats['ideas']} | Prompts: {stats['prompts']}\n")
    return result


def main():
    parser = argparse.ArgumentParser(description="Autonomous Prompt Fillup Loop Engine")
    parser.add_argument("--skip-browser", action="store_true", help="Skip live browser launch and test resolution logic")
    parser.add_argument("--count", type=int, default=0, help="Number of cycles to run (0 = infinite continuous loop)")
    parser.add_argument("--loop", action="store_true", default=True, help="Run continuously in loop")
    parser.add_argument("--delay", type=int, default=3, help="Cooldown delay in seconds between fresh Chrome browser cycles (default: 3s)")
    args = parser.parse_args()

    init_db()
    stats = get_current_pipeline_stats()
    print("=" * 80)
    print("       🚀 AUTONOMOUS PROMPT FILLUP LOOP ENGINE (PART 1)")
    print("=" * 80)
    print(f"  • Initial Database Stats: {stats['elements']} Elements | {stats['ideas']} Ideas | {stats['prompts']} Prompts")
    print(f"  • Mode:                   {'Finite Count: ' + str(args.count) if args.count > 0 else 'Continuous Autonomous Loop'}")
    print(f"  • Browser Mode:           {'Skip Browser (Fast Test)' if args.skip_browser else 'Fresh Chrome per Cycle'}")
    print(f"  • Cycle Delay:            {args.delay} seconds")
    print("=" * 80)

    cycle = 1
    try:
        while True:
            res = run_single_fillup(skip_browser=args.skip_browser, cycle_num=cycle)
            
            if args.count > 0 and cycle >= args.count:
                print(f"\n🎉 Completed requested {args.count} cycle(s). Stopping loop.")
                break

            print(f"⏳ Waiting {args.delay}s before starting next fresh Chrome cycle (Cycle #{cycle + 1})... (Press Ctrl+C to stop)")
            time.sleep(args.delay)
            cycle += 1

    except KeyboardInterrupt:
        print("\n\n🛑 Loop gracefully stopped by user.")
        print(f"Total cycles completed in this session: {cycle - 1}")


if __name__ == "__main__":
    main()

