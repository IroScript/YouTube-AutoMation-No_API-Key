"""
Master Autonomous Video Pipeline Packager (1Video10Sec Workflow)
================================================================
1. Dynamic Hierarchical Folder Naming: <Element_ID>.<Idea_Index_In_Element>.Level_10_<Title>
   (e.g., 1.1.Level_10_Rice_Titan_Harvester, 1.2.Level_10_The_Paddy_Ocean_Vacuum)
2. Strict SQLite-First Architecture:
   - YouTube SEO Metadata (Title, Description, Tags) is generated and stored directly into SQLite `youtube_metadata` table.
   - All exported files (`prompt_info.json`, `youtube_metadata.json`) originate directly from SQLite.
3. No-Real-Video = No-Folder Guarantee:
   - The package folder is ONLY created and preserved if a real generated MP4 video (>10KB) exists.
   - If no video is generated yet, no folder exists on disk.
4. Strict No-Retry Lock:
   - If real .mp4, youtube_metadata.json, and prompt_info.json exist, skips retry and marks status SUCCESS.
"""

import sys
import os
import re
import json
import uuid
import time
import shutil
from datetime import datetime, timezone
from pathlib import Path
from sqlmodel import select

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.session import init_db, get_session
from database.models import Idea, IdeaElement, Element, Prompt, Task, TaskAttempt, GeneratedVideo, YouTubeMetadata
from playwright_engine.generate_youtube_metadata import fetch_youtube_metadata_via_playwright
from prompt_chain_engine import get_or_create_next_production_ready_prompt, is_idea_packaged_and_completed

OUTPUT_PACKAGED_DIR = BASE_DIR / "output_packaged"
OUTPUT_PACKAGED_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    return re.sub(r'_+', '_', clean).strip('_')


def get_idea_package_folder_name(idea_id: int, session) -> str:
    """
    Returns hierarchical folder name in format:
      <Element_ID>.<Idea_Index_In_Element>.Level_10_<Sanitized_Title>
    e.g. 1.1.Level_10_Rice_Titan_Harvester, 1.2.Level_10_The_Paddy_Ocean_Vacuum
    """
    idea = session.exec(select(Idea).where(Idea.id == idea_id)).first()
    if not idea:
        return f"Idea_{idea_id}"

    # Get linked element
    idea_element = session.exec(select(IdeaElement).where(IdeaElement.idea_id == idea.id)).first()
    elem_id = idea_element.element_id if idea_element else 1

    # Find idea index within this element
    linked_ideas = session.exec(
        select(Idea).join(IdeaElement).where(IdeaElement.element_id == elem_id).order_by(Idea.id)
    ).all()

    idea_idx = 1
    for idx, i in enumerate(linked_ideas, 1):
        if i.id == idea.id:
            idea_idx = idx
            break

    safe_title = sanitize_filename(idea.title)
    return f"{elem_id}.{idea_idx}.Level_10_{safe_title}"


def sync_and_get_youtube_metadata_from_sqlite(idea: Idea, elem_id: int, vid_p: Prompt, img_p: Prompt, session, skip_browser: bool = False) -> YouTubeMetadata:
    """
    Ensures YouTube SEO metadata is saved and tracked directly in SQLite `youtube_metadata` table.
    """
    yt_rec = session.exec(select(YouTubeMetadata).where(YouTubeMetadata.idea_id == idea.id)).first()
    if yt_rec:
        return yt_rec

    print(f"[SQLite SEO Sync] Generating and saving YouTube Metadata to SQLite for Idea #{idea.id} '{idea.title}'...")
    raw_meta = fetch_youtube_metadata_via_playwright(idea.title, topic=idea.topic or "", skip_browser=skip_browser)

    yt_rec = YouTubeMetadata(
        uuid=str(uuid.uuid4()),
        idea_id=idea.id,
        element_id=elem_id,
        title=raw_meta.get("title", f"🚨 INSANE: {idea.title} - Level 10 Impossible Megastructure 🌾"),
        seo_description=raw_meta.get("seo_description", ""),
        tags=json.dumps(raw_meta.get("tags", []), ensure_ascii=False),
        category=raw_meta.get("category", "Science & Technology"),
        default_language=raw_meta.get("default_language", "en"),
        video_prompt_used=vid_p.prompt_text if vid_p else "",
        image_prompt_used=img_p.prompt_text if img_p else "",
        status="ready"
    )
    session.add(yt_rec)
    session.commit()
    session.refresh(yt_rec)
    print(f"[SQLite SEO Sync] YouTube Metadata successfully stored in SQLite table `youtube_metadata` (ID: #{yt_rec.id}).")
    return yt_rec


def export_package_files_from_sqlite(idea: Idea, elem_id: int, idea_idx: int, vid_p: Prompt, img_p: Prompt, package_folder: Path, session):
    """
    Exports `prompt_info.json` and `youtube_metadata.json` directly from SQLite tables into the package folder.
    """
    package_folder.mkdir(parents=True, exist_ok=True)

    # 1. Export prompt json from SQLite prompts table
    prompt_info_data = {
        "idea_id": idea.id,
        "idea_title": idea.title,
        "idea_topic": idea.topic,
        "element_id": elem_id,
        "idea_index_in_element": idea_idx,
        "target_generation": "10-Second Veo Video",
        "escalation_level": 10,
        "level_name": vid_p.level_name if vid_p else "ALIEN LEVEL / MAXIMUM",
        "primary_video_prompt_used": vid_p.prompt_text if vid_p else "",
        "video_prompt_title": vid_p.title if vid_p else "",
        "model": "Veo 3.1 Lower Priority / 1Video10Sec",
        "duration": "8s",
        "aspect_ratio": "9:16",
        "reference_image_prompt": img_p.prompt_text if img_p else "",
        "source_pipeline": "PromptDatabase Hierarchical Chain (SQLite Verified)",
        "exported_from_sqlite_at": datetime.now(timezone.utc).isoformat()
    }
    prompt_info_path = package_folder / f"{elem_id}.{idea_idx}.Level_10_Prompt.json"
    with open(prompt_info_path, "w", encoding="utf-8") as pf:
        json.dump(prompt_info_data, pf, indent=2, ensure_ascii=False)
    # Also save standard prompt_info.json
    with open(package_folder / "prompt_info.json", "w", encoding="utf-8") as pf:
        json.dump(prompt_info_data, pf, indent=2, ensure_ascii=False)
    print(f"[SQLite Export] Saved {prompt_info_path}")

    # 2. Export youtube_metadata.json directly from SQLite youtube_metadata table
    yt_rec = session.exec(select(YouTubeMetadata).where(YouTubeMetadata.idea_id == idea.id)).first()
    if yt_rec:
        try:
            tags_list = json.loads(yt_rec.tags) if yt_rec.tags else []
        except Exception:
            tags_list = [t.strip() for t in yt_rec.tags.split(",") if t.strip()]

        yt_meta_data = {
            "title": yt_rec.title,
            "seo_description": yt_rec.seo_description,
            "tags": tags_list,
            "category": yt_rec.category,
            "default_language": yt_rec.default_language,
            "source": "sqlite_youtube_metadata_table",
            "exported_at": datetime.now(timezone.utc).isoformat()
        }
        metadata_path = package_folder / f"{elem_id}.{idea_idx}.Level_10_YouTube_Metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as mf:
            json.dump(yt_meta_data, mf, indent=2, ensure_ascii=False)
        # Also save standard youtube_metadata.json
        with open(package_folder / "youtube_metadata.json", "w", encoding="utf-8") as mf:
            json.dump(yt_meta_data, mf, indent=2, ensure_ascii=False)
        print(f"[SQLite Export] Saved {metadata_path}")


def process_idea_level10_package(idea_id: int, skip_browser: bool = False) -> dict:
    init_db()

    with get_session() as session:
        idea = session.exec(select(Idea).where(Idea.id == idea_id)).first()
        if not idea:
            raise ValueError(f"Idea #{idea_id} not found in database!")

        vid_p = session.exec(select(Prompt).where(
            Prompt.idea_id == idea_id,
            Prompt.level == 10,
            Prompt.generation_type == "video"
        )).first()

        img_p = session.exec(select(Prompt).where(
            Prompt.idea_id == idea_id,
            Prompt.level == 10,
            Prompt.generation_type == "image"
        )).first()

        # 1. Determine hierarchical folder name: <Element_ID>.<Idea_Index_In_Element>.Level_10_<Title>
        folder_name = get_idea_package_folder_name(idea_id, session)
        package_folder = OUTPUT_PACKAGED_DIR / folder_name
        video_filename = f"{folder_name}.mp4"
        video_filepath = package_folder / video_filename
        metadata_filepath = package_folder / "youtube_metadata.json"
        prompt_info_filepath = package_folder / "prompt_info.json"

        # Determine element id and idea index
        idea_elem = session.exec(select(IdeaElement).where(IdeaElement.idea_id == idea.id)).first()
        elem_id = idea_elem.element_id if idea_elem else 1
        linked_ideas = session.exec(
            select(Idea).join(IdeaElement).where(IdeaElement.element_id == elem_id).order_by(Idea.id)
        ).all()
        idea_idx = 1
        for idx, i in enumerate(linked_ideas, 1):
            if i.id == idea.id:
                idea_idx = idx
                break

        # 2. Sync YouTube SEO Metadata into SQLite table first
        yt_meta_rec = sync_and_get_youtube_metadata_from_sqlite(idea, elem_id, vid_p, img_p, session, skip_browser=skip_browser)

        # 3. Check Task tracking in SQLite
        task = session.exec(select(Task).where(
            Task.idea_id == idea_id,
            Task.task_type == "veo_level10_package"
        )).first()

        if not task:
            task = Task(
                uuid=str(uuid.uuid4()),
                idea_id=idea_id,
                prompt_id=vid_p.id if vid_p else (img_p.id if img_p else None),
                video_title=f"{idea.title} (Level 10 Alien Megastructure)",
                task_type="veo_level10_package",
                status="pending",
                attempt_count=0,
                max_attempts=3,
                output_folder_path=str(package_folder),
                video_path=str(video_filepath),
                metadata_json_path=str(metadata_filepath)
            )
            session.add(task)
            session.commit()
            session.refresh(task)

        # 4. Strict No-Retry Check (Real Video > 10KB + YouTube Metadata + Prompt Info)
        video_exists = video_filepath.exists() and video_filepath.stat().st_size > 10240
        metadata_exists = metadata_filepath.exists() and metadata_filepath.stat().st_size > 0
        prompt_info_exists = prompt_info_filepath.exists() and prompt_info_filepath.stat().st_size > 0

        # If real video exists on disk but JSON exports are missing, rebuild them from SQLite
        if video_exists and (not metadata_exists or not prompt_info_exists):
            print(f"[Auto-Rebuild] Rebuilding missing package JSONs from SQLite for Idea #{idea_id}...")
            export_package_files_from_sqlite(idea, elem_id, idea_idx, vid_p, img_p, package_folder, session)
            metadata_exists = True
            prompt_info_exists = True

        if video_exists and metadata_exists and prompt_info_exists:
            print("=" * 65)
            print(f"[NO-RETRY LOCK] Idea #{idea_id} '{idea.title}' is ALREADY 100% COMPLETE & PACKAGED!")
            print(f"  Folder:      {package_folder}")
            print(f"  Real Video:  {video_filepath} ({video_filepath.stat().st_size} bytes)")
            print(f"  Metadata:    {metadata_filepath} (From SQLite)")
            print(f"  Prompt Info: {prompt_info_filepath} (From SQLite)")
            print(f"  -> Skipping retry. Status confirmed as SUCCESS.")
            print("=" * 65)

            if task.status != "success":
                task.status = "success"
                task.updated_at = datetime.now(timezone.utc)
                session.add(task)
                session.commit()

            return {
                "status": "already_completed",
                "idea_id": idea_id,
                "folder": str(package_folder),
                "video": str(video_filepath),
                "metadata": str(metadata_filepath),
                "prompt_info": str(prompt_info_filepath)
            }

        # 5. Attempt Execution & Real Video Integration
        task.attempt_count += 1
        task.status = "running"
        session.add(task)
        session.commit()

        attempt = TaskAttempt(
            task_id=task.id,
            attempt_number=task.attempt_count,
            status="running",
            input_data=json.dumps({
                "idea_id": idea_id,
                "idea_title": idea.title,
                "video_prompt": vid_p.prompt_text if vid_p else "",
                "image_prompt": img_p.prompt_text if img_p else "",
                "target_folder": str(package_folder)
            }),
            started_at=datetime.now(timezone.utc)
        )
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        print(f"\n[Packaging Engine] Executing Attempt #{task.attempt_count} for Idea #{idea_id}: '{idea.title}'...")

        try:
            # 6. Verify if a newly rendered video is recorded in SQLite generated_videos table
            gen_video_rec = session.exec(
                select(GeneratedVideo).where(GeneratedVideo.idea_id == idea.id, GeneratedVideo.status == "completed")
            ).first()
            real_video_found = None
            if gen_video_rec and gen_video_rec.file_path and os.path.exists(gen_video_rec.file_path):
                if os.path.getsize(gen_video_rec.file_path) > 10240:
                    real_video_found = Path(gen_video_rec.file_path)

            # 🛑 CRITICAL RULE: Video Na Thakle Folder Er Kono Ostitto Thakbe Naa
            if not real_video_found:
                # If an empty or incomplete folder exists, remove it immediately
                if package_folder.exists():
                    shutil.rmtree(package_folder, ignore_errors=True)

                task.status = "waiting_for_video"
                task.last_error = "Real MP4 video not yet available on Google Flow / 1Video10Sec. Folder creation deferred."
                task.updated_at = datetime.now(timezone.utc)
                attempt.status = "waiting_for_video"
                attempt.error_message = task.last_error
                attempt.finished_at = datetime.now(timezone.utc)
                session.add(task)
                session.add(attempt)
                session.commit()

                print(f"\n⚠️ [NO VIDEO -> NO FOLDER] Real MP4 video is not yet ready for Idea #{idea_id} '{idea.title}'.")
                print(f"  -> Folder '{folder_name}' will NOT be created until the real video is generated!")
                return {
                    "status": "waiting_for_video",
                    "idea_id": idea_id,
                    "folder": None,
                    "video": None,
                    "message": "Real video pending from 1Video10Sec / Veo"
                }

            # ✅ Real Video IS available -> Now create folder and copy video
            print(f"[Veo Video] Integrating Real Level 10 video ({real_video_found.stat().st_size} bytes)...")
            package_folder.mkdir(parents=True, exist_ok=True)
            shutil.copy(real_video_found, video_filepath)

            # Export JSON files directly from SQLite
            export_package_files_from_sqlite(idea, elem_id, idea_idx, vid_p, img_p, package_folder, session)

            # Update SQLite Tracking
            task.status = "success"
            task.updated_at = datetime.now(timezone.utc)
            task.last_error = None

            attempt.status = "success"
            attempt.output_data = json.dumps({
                "folder": str(package_folder),
                "video": str(video_filepath),
                "metadata": str(metadata_filepath),
                "prompt_info": str(prompt_info_filepath)
            })
            attempt.finished_at = datetime.now(timezone.utc)

            # Record in generated_videos table in SQLite
            gen_video = session.exec(select(GeneratedVideo).where(GeneratedVideo.idea_id == idea.id)).first()
            if not gen_video:
                gen_video = GeneratedVideo(
                    uuid=str(uuid.uuid4()),
                    idea_id=idea.id,
                    title=idea.title,
                    file_path=str(video_filepath),
                    file_name=video_filename,
                    file_size_bytes=video_filepath.stat().st_size,
                    duration_seconds=8.0,
                    resolution="1080x1920",
                    status="completed"
                )
                session.add(gen_video)

            yt_meta_rec.video_file_path = str(video_filepath)
            yt_meta_rec.package_folder_path = str(package_folder)
            yt_meta_rec.updated_at = datetime.now(timezone.utc)
            session.add(yt_meta_rec)

            idea.status = "ready_for_upload"
            idea.generated_at = datetime.now(timezone.utc)
            session.add(idea)
            session.add(task)
            session.add(attempt)
            session.commit()

            print(f"[Packaging Complete] Idea #{idea_id} ({folder_name}) successfully packaged! 100% DONE & LOCKED (NO RETRY).")
            return {
                "status": "success",
                "idea_id": idea_id,
                "folder": str(package_folder),
                "video": str(video_filepath),
                "metadata": str(metadata_filepath),
                "prompt_info": str(prompt_info_filepath)
            }

        except Exception as e:
            task.status = "failed" if task.attempt_count < task.max_attempts else "permanent_failure"
            task.last_error = str(e)
            task.updated_at = datetime.now(timezone.utc)

            attempt.status = "failed"
            attempt.error_message = str(e)
            attempt.finished_at = datetime.now(timezone.utc)

            session.add(task)
            session.add(attempt)
            session.commit()
            print(f"[Packaging Error]: {e}")
            raise


def run_next_level10_package(skip_browser: bool = False):
    print("=" * 70)
    print("AUTONOMOUS VEO PACKAGING: FETCHING NEXT PRODUCTION READY ITEM")
    print("=" * 70)
    ready_item = get_or_create_next_production_ready_prompt(skip_browser=skip_browser)
    idea_id = ready_item["idea_id"]
    print(f"\n[Packaging Engine] Packaging Idea #{idea_id}: '{ready_item['idea_title']}'...")
    res = process_idea_level10_package(idea_id, skip_browser=skip_browser)
    return res


def run_all_level10_packaging_loop(skip_browser: bool = False):
    print("=" * 65)
    print("AUTONOMOUS LEVEL 10 VEO PACKAGING & NO-RETRY ENGINE")
    print("=" * 65)
    init_db()
    with get_session() as session:
        ideas = session.exec(select(Idea).order_by(Idea.id)).all()
        print(f"Total Ideas in Database: {len(ideas)}")

    for idea in ideas:
        print(f"\n---> Checking Idea #{idea.id}: '{idea.title}'...")
        res = process_idea_level10_package(idea.id, skip_browser=skip_browser)
        print(f"Result: {res['status']}")

    print("\n" + "=" * 65)
    print("ALL LEVEL 10 PACKAGING COMPLETED & VERIFIED!")
    print("=" * 65)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Level 10 Video Packager")
    parser.add_argument("--next", action="store_true", help="Process only the next production-ready idea")
    parser.add_argument("--idea-id", type=int, default=None, help="Process specific Idea ID")
    parser.add_argument("--skip-browser", action="store_true", help="Skip browser for fast dry-run")
    args = parser.parse_args()

    if args.idea_id:
        process_idea_level10_package(args.idea_id, skip_browser=args.skip_browser)
    elif args.next:
        run_next_level10_package(skip_browser=args.skip_browser)
    else:
        run_all_level10_packaging_loop(skip_browser=args.skip_browser)
