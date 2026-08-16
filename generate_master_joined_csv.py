r"""
Unified Master CSV Generator - All Relational Database Tables Joined
=====================================================================
Joins all tables across the hierarchy into a single Master CSV:
  - categories
  - elements
  - idea_elements
  - ideas
  - prompts (Level 1 to 10 Image & Video prompts)
  - tasks
  - task_attempts
  - generated_videos
  - output_packaged filesystem verification
"""

import sys
import os
import csv
import json
import sqlite3
from pathlib import Path
from sqlmodel import select

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.session import init_db, get_session, DB_PATH
from database.models import Category, Element, Idea, IdeaElement, Prompt, Task, TaskAttempt, GeneratedVideo

EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
MASTER_CSV_PATH = EXPORT_DIR / "unified_master_pipeline.csv"
OUTPUT_PACKAGED_DIR = BASE_DIR / "output_packaged"


def generate_unified_master_csv():
    init_db()
    
    with get_session() as session:
        elements = session.exec(select(Element).order_by(Element.id.asc())).all()
        categories = session.exec(select(Category)).all()
        cat_map = {c.id: c.name for c in categories}
        cat_default = categories[0].name if categories else "Impossible Giant Machine"

        all_ideas = session.exec(select(Idea).order_by(Idea.id.asc())).all()
        all_prompts = session.exec(select(Prompt).order_by(Prompt.idea_id.asc(), Prompt.level.asc(), Prompt.generation_type.asc())).all()
        all_tasks = session.exec(select(Task)).all()
        all_attempts = session.exec(select(TaskAttempt).order_by(TaskAttempt.id.asc())).all()
        all_videos = session.exec(select(GeneratedVideo)).all()
        all_links = session.exec(select(IdeaElement)).all()

    # Create fast index lookup maps
    idea_elem_map = {}
    for link in all_links:
        idea_elem_map.setdefault(link.element_id, []).append(link.idea_id)

    prompts_by_idea = {}
    for p in all_prompts:
        prompts_by_idea.setdefault(p.idea_id, []).append(p)

    task_by_idea = {t.idea_id: t for t in all_tasks if t.idea_id}
    
    attempts_by_task = {}
    for att in all_attempts:
        attempts_by_task.setdefault(att.task_id, []).append(att)

    video_by_idea = {v.idea_id: v for v in all_videos if v.idea_id}
    idea_by_id = {i.id: i for i in all_ideas}

    rows = []

    for elem in elements:
        cat_name = cat_map.get(1, cat_default)
        linked_idea_ids = idea_elem_map.get(elem.id, [])

        if not linked_idea_ids:
            # Row for Element without ideas yet
            rows.append({
                "Category_ID": 1,
                "Category_Name": cat_name,
                "Element_ID": elem.id,
                "Element_Name": elem.name,
                "Element_Group": elem.group_type or "",
                "Element_Status": "FILLED_IN_DB",
                "Idea_ID": "",
                "Idea_Title": "[BLANK - Needs 10 Ideas]",
                "Idea_Topic": elem.name,
                "Idea_Niche": "",
                "Idea_Status": "BLANK",
                "Total_Prompts_For_Idea": 0,
                "Prompt_ID": "",
                "Prompt_Level": "",
                "Prompt_Level_Name": "",
                "Prompt_Type": "",
                "Prompt_Generation_Type": "",
                "Prompt_Aspect_Ratio": "",
                "Prompt_Duration_Sec": "",
                "Prompt_Text": "",
                "Prompt_Status": "BLANK",
                "Task_ID": "",
                "Task_Type": "",
                "Task_Status": "PENDING_IDEAS",
                "Task_Attempt_Count": 0,
                "Task_Max_Attempts": 3,
                "Latest_Attempt_Status": "",
                "Latest_Attempt_Error": "",
                "Output_Folder_Path": "",
                "Output_Video_File_Exists": "NO",
                "Output_Metadata_JSON_Exists": "NO",
                "No_Retry_Locked": "NO",
                "Pipeline_Lifecycle_State": "WAITING_FOR_ELEMENT_IDEAS"
            })
            continue

        for idea_id in linked_idea_ids:
            idea = idea_by_id.get(idea_id)
            if not idea:
                continue

            idea_prompts = prompts_by_idea.get(idea.id, [])
            task = task_by_idea.get(idea.id)
            task_attempts = attempts_by_task.get(task.id, []) if task else []
            latest_attempt = task_attempts[-1] if task_attempts else None
            vid = video_by_idea.get(idea.id)

            # Filesystem check
            folder_exists = "NO"
            mp4_exists = "NO"
            json_exists = "NO"
            is_locked = "NO"

            if task and task.output_folder_path:
                p = Path(task.output_folder_path)
                if p.exists() and p.is_dir():
                    folder_exists = "YES"
                    if list(p.glob("*.mp4")):
                        mp4_exists = "YES"
                    if (p / "youtube_metadata.json").exists():
                        json_exists = "YES"
                    if mp4_exists == "YES" and json_exists == "YES":
                        is_locked = "YES (LOCKED - NO RETRY)"

            lifecycle_state = "COMPLETED_AND_PACKAGED" if is_locked.startswith("YES") else (
                "READY_FOR_VIDEO_PACKAGING" if any(p.level == 10 and p.generation_type == "video" for p in idea_prompts) else (
                    "PROMPTS_GENERATING" if idea_prompts else "WAITING_FOR_PROMPT_ESCALATION"
                )
            )

            if not idea_prompts:
                # Idea with 0 prompts
                rows.append({
                    "Category_ID": idea.category_id or 1,
                    "Category_Name": cat_name,
                    "Element_ID": elem.id,
                    "Element_Name": elem.name,
                    "Element_Group": elem.group_type or "",
                    "Element_Status": "FILLED_IN_DB",
                    "Idea_ID": idea.id,
                    "Idea_Title": idea.title,
                    "Idea_Topic": idea.topic or elem.name,
                    "Idea_Niche": idea.niche or "",
                    "Idea_Status": idea.status or "new",
                    "Total_Prompts_For_Idea": 0,
                    "Prompt_ID": "",
                    "Prompt_Level": "",
                    "Prompt_Level_Name": "",
                    "Prompt_Type": "",
                    "Prompt_Generation_Type": "",
                    "Prompt_Aspect_Ratio": "",
                    "Prompt_Duration_Sec": "",
                    "Prompt_Text": "",
                    "Prompt_Status": "BLANK",
                    "Task_ID": task.id if task else "",
                    "Task_Type": task.task_type if task else "",
                    "Task_Status": task.status if task else "NOT_STARTED",
                    "Task_Attempt_Count": task.attempt_count if task else 0,
                    "Task_Max_Attempts": task.max_attempts if task else 3,
                    "Latest_Attempt_Status": latest_attempt.status if latest_attempt else "",
                    "Latest_Attempt_Error": latest_attempt.error_message if latest_attempt else "",
                    "Output_Folder_Path": task.output_folder_path if task else "",
                    "Output_Video_File_Exists": mp4_exists,
                    "Output_Metadata_JSON_Exists": json_exists,
                    "No_Retry_Locked": is_locked,
                    "Pipeline_Lifecycle_State": lifecycle_state
                })
            else:
                # Iterate through all 20 prompts for full relational joining
                for prompt in idea_prompts:
                    rows.append({
                        "Category_ID": idea.category_id or 1,
                        "Category_Name": cat_name,
                        "Element_ID": elem.id,
                        "Element_Name": elem.name,
                        "Element_Group": elem.group_type or "",
                        "Element_Status": "FILLED_IN_DB",
                        "Idea_ID": idea.id,
                        "Idea_Title": idea.title,
                        "Idea_Topic": idea.topic or elem.name,
                        "Idea_Niche": idea.niche or "",
                        "Idea_Status": idea.status or "new",
                        "Total_Prompts_For_Idea": len(idea_prompts),
                        "Prompt_ID": prompt.id,
                        "Prompt_Level": prompt.level or "",
                        "Prompt_Level_Name": prompt.level_name or "",
                        "Prompt_Type": prompt.prompt_type or "",
                        "Prompt_Generation_Type": prompt.generation_type or "",
                        "Prompt_Aspect_Ratio": prompt.aspect_ratio or "16:9",
                        "Prompt_Duration_Sec": prompt.duration_seconds or "",
                        "Prompt_Text": prompt.prompt_text or "",
                        "Prompt_Status": prompt.status or "ready",
                        "Task_ID": task.id if task else "",
                        "Task_Type": task.task_type if task else "",
                        "Task_Status": task.status if task else "NOT_STARTED",
                        "Task_Attempt_Count": task.attempt_count if task else 0,
                        "Task_Max_Attempts": task.max_attempts if task else 3,
                        "Latest_Attempt_Status": latest_attempt.status if latest_attempt else "",
                        "Latest_Attempt_Error": latest_attempt.error_message if latest_attempt else "",
                        "Output_Folder_Path": task.output_folder_path if task else "",
                        "Output_Video_File_Exists": mp4_exists,
                        "Output_Metadata_JSON_Exists": json_exists,
                        "No_Retry_Locked": is_locked,
                        "Pipeline_Lifecycle_State": lifecycle_state
                    })

    # Write unified master CSV safely
    if rows:
        fieldnames = list(rows[0].keys())
        try:
            with open(MASTER_CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            target_path = MASTER_CSV_PATH
        except PermissionError:
            fallback_path = EXPORT_DIR / "unified_master_pipeline_updated.csv"
            with open(fallback_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            target_path = fallback_path
            print(f"[Notice] '{MASTER_CSV_PATH.name}' is currently open in another app (e.g. Excel). Saved updated version to: {fallback_path.name}")

    print(f"\n[Success] Unified Master CSV generated successfully!")
    print(f"  Path: {target_path}")
    print(f"  Total Rows: {len(rows)}")
    print(f"  Total Columns: {len(fieldnames) if rows else 0}\n")
    return rows


if __name__ == "__main__":
    generate_unified_master_csv()
