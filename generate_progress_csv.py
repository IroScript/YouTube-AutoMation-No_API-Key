"""
Hierarchical Pipeline CSV & Progress Tracker Generator (Clean)
==============================================================
1. Generates `pipeline_hierarchy_progress.csv` showing the exact Fillup Lifecycle
   (Blank vs Filled) for Categories -> Elements -> Ideas -> 1-10 Prompts -> Video Packages -> Retry Status.
2. Generates `table_fillup_summary.csv` showing table-by-table record counts and fill rates.
3. Refreshes all 29 raw database table CSVs into `exports/csv_tables/`.
"""

import sys
import os
import csv
import sqlite3
from pathlib import Path
from sqlmodel import select

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.session import init_db, get_session, DB_PATH
from database.models import Category, Element, Idea, IdeaElement, Prompt, Task, TaskAttempt, GeneratedVideo

EXPORT_DIR = BASE_DIR / "exports"
CSV_TABLES_DIR = EXPORT_DIR / "csv_tables"
PROGRESS_CSV_PATH = EXPORT_DIR / "pipeline_hierarchy_progress.csv"
SUMMARY_CSV_PATH = EXPORT_DIR / "table_fillup_summary.csv"
OUTPUT_PACKAGED_DIR = BASE_DIR / "output_packaged"


def export_raw_tables(db_path: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name ASC")
    tables = [row[0] for row in cur.fetchall() if not row[0].startswith('sqlite_')]

    table_summaries = []
    for tbl in tables:
        cur.execute(f'SELECT * FROM "{tbl}"')
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description] if cur.description else []

        csv_file = output_dir / f"{tbl}.csv"
        with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            writer.writerows(rows)

        table_summaries.append({
            "table_name": tbl,
            "row_count": len(rows),
            "col_count": len(cols),
            "csv_path": str(csv_file)
        })
    conn.close()
    return table_summaries


def generate_pipeline_hierarchy_progress():
    init_db()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    with get_session() as session:
        elements = session.exec(select(Element).order_by(Element.id.asc())).all()
        categories = session.exec(select(Category)).all()
        cat_name = categories[0].name if categories else "Impossible Giant Machine"

        rows = []
        for elem in elements:
            idea_links = session.exec(select(IdeaElement).where(IdeaElement.element_id == elem.id)).all()
            linked_idea_ids = [il.idea_id for il in idea_links]

            if not linked_idea_ids:
                rows.append({
                    "Category": cat_name,
                    "Element_ID": elem.id,
                    "Element_Name": elem.name,
                    "Element_Group": elem.group_type,
                    "Element_Status": "FILLED (1/1)",
                    "Idea_ID": "[BLANK - Pending Ideas]",
                    "Idea_Title": "[BLANK - Needs 10 Ideas]",
                    "Idea_Status": "BLANK (0/10)",
                    "Prompts_Count": "0/20 [BLANK]",
                    "Level_10_Prompt_Status": "BLANK",
                    "Video_Package_Status": "BLANK",
                    "Task_Status": "PENDING_IDEAS",
                    "Attempt_Count": 0,
                    "No_Retry_Lock": "NO",
                    "Next_Action": "Run Idea Generator to fill 10 Ideas"
                })
                continue

            for idea_id in linked_idea_ids:
                idea = session.exec(select(Idea).where(Idea.id == idea_id)).first()
                if not idea:
                    continue

                prompts = session.exec(select(Prompt).where(Prompt.idea_id == idea.id)).all()
                prompt_count = len(prompts)

                lvl10_vid = [p for p in prompts if p.level == 10 and p.generation_type == "video"]
                lvl10_status = "READY (Level 10 Video Prompt Active)" if lvl10_vid else "BLANK (Needs 1-10 Escalation)"

                task = session.exec(select(Task).where(Task.idea_id == idea.id)).first()
                attempts_count = task.attempt_count if task else 0
                task_status = task.status if task else "NOT_STARTED"

                is_packaged = False
                if task and task.output_folder_path:
                    p = Path(task.output_folder_path)
                    if p.exists() and list(p.glob("*.mp4")) and (p / "youtube_metadata.json").exists():
                        is_packaged = True

                if is_packaged:
                    video_pkg_status = "COMPLETED (MP4 + JSON Present)"
                    no_retry = "YES (LOCKED - NO RETRY)"
                    next_action = "DONE & VERIFIED"
                elif lvl10_vid:
                    video_pkg_status = "READY_FOR_PACKAGING"
                    no_retry = "NO"
                    next_action = "Run Video Packager"
                else:
                    video_pkg_status = "BLANK"
                    no_retry = "NO"
                    next_action = "Run Prompt Escalation Fillup"

                rows.append({
                    "Category": cat_name,
                    "Element_ID": elem.id,
                    "Element_Name": elem.name,
                    "Element_Group": elem.group_type,
                    "Element_Status": f"FILLED ({len(linked_idea_ids)} Ideas Linked)",
                    "Idea_ID": idea.id,
                    "Idea_Title": idea.title,
                    "Idea_Status": "FILLED",
                    "Prompts_Count": f"{prompt_count}/20 ({'FILLED' if prompt_count >= 20 else 'BLANK'})",
                    "Level_10_Prompt_Status": lvl10_status,
                    "Video_Package_Status": video_pkg_status,
                    "Task_Status": task_status,
                    "Attempt_Count": attempts_count,
                    "No_Retry_Lock": no_retry,
                    "Next_Action": next_action
                })

    # Write Master Progress CSV safely
    if rows:
        fieldnames = list(rows[0].keys())
        try:
            with open(PROGRESS_CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        except PermissionError:
            fallback = EXPORT_DIR / "pipeline_hierarchy_progress_updated.csv"
            with open(fallback, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"[Notice] '{PROGRESS_CSV_PATH.name}' is open in another app. Saved to '{fallback.name}'.")

    return rows


def generate_table_fillup_summary(table_summaries: list):
    fieldnames = ["Table_Name", "Row_Count", "Column_Count", "Status", "CSV_Path"]
    summary_rows = []
    for ts in table_summaries:
        status = "FILLED" if ts["row_count"] > 0 else "BLANK / EMPTY"
        summary_rows.append({
            "Table_Name": ts["table_name"],
            "Row_Count": ts["row_count"],
            "Column_Count": ts["col_count"],
            "Status": status,
            "CSV_Path": ts["csv_path"]
        })

    try:
        with open(SUMMARY_CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summary_rows)
    except PermissionError:
        fallback = EXPORT_DIR / "table_fillup_summary_updated.csv"
        with open(fallback, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summary_rows)


from generate_master_joined_csv import generate_unified_master_csv, MASTER_CSV_PATH


def run():
    print("=" * 75)
    print("AUTONOMOUS PROGRESS & BLANK-VS-FILLED CSV GENERATOR")
    print("=" * 75)
    
    table_summaries = export_raw_tables(DB_PATH, CSV_TABLES_DIR)
    generate_table_fillup_summary(table_summaries)
    progress_rows = generate_pipeline_hierarchy_progress()
    master_rows = generate_unified_master_csv()

    # Copy prompting_style_master.csv to top-level exports folder for easy access
    src_style_csv = CSV_TABLES_DIR / "prompting_style_master.csv"
    dst_style_csv = EXPORT_DIR / "prompting_style_master.csv"
    if src_style_csv.exists():
        import shutil
        shutil.copy(src_style_csv, dst_style_csv)

    print("\n" + "=" * 75)
    print("✅ ALL CSV EXPORTS & MASTER JOINED TABLE GENERATION COMPLETE!")
    print(f"  • 🌟 UNIFIED MASTER CSV (ALL TABLES JOINED): {MASTER_CSV_PATH}")
    print(f"  • 📜 PROMPTING STYLE MASTER CSV:             {dst_style_csv}")
    print(f"  • Master Progress CSV (Blank vs Filled):     {PROGRESS_CSV_PATH}")
    print(f"  • Table Summary CSV:                         {SUMMARY_CSV_PATH}")
    print(f"  • Raw Tables CSVs:                           {CSV_TABLES_DIR}")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run()
