"""
YouTube Pipeline Database Schema (Clean Standalone Models)
==========================================================
Hierarchical Levels:
  Level 1 (Root):   Category (e.g. 'Impossible Giant Machine')
  Level 2:          Element (100 Elements, auto-generating #101+)
  Level 3:          Idea (10 Ideas per Element) & IdeaElement
  Level 4:          Prompt (10-Level Escalation: 10 Image + 10 Video Prompts = 20 Prompts)
  Level 5:          Task & TaskAttempt (Stateful Retries with Strict No-Retry Lock)
"""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel, Column, JSON


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class YouTubeBaseModel(SQLModel):
    pass


class Category(YouTubeBaseModel, table=True):
    __tablename__ = "categories"

    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: str = Field(index=True, unique=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


class Element(YouTubeBaseModel, table=True):
    __tablename__ = "elements"

    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: str = Field(index=True, unique=True)
    name: str = Field(index=True, unique=True)
    symbol: Optional[str] = None
    group_type: Optional[str] = None  # Nature, Agriculture, Space, Tech, Environment, etc.
    created_at: datetime = Field(default_factory=_utcnow)


class Idea(YouTubeBaseModel, table=True):
    __tablename__ = "ideas"

    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: str = Field(index=True, unique=True)
    title: str
    short_title: Optional[str] = None
    raw_idea: str
    refined_idea: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = Field(default=None, foreign_key="categories.id", index=True)
    category: Optional[str] = None
    subcategory: Optional[str] = None
    topic: Optional[str] = None
    niche: Optional[str] = None
    content_type: Optional[str] = None
    format: Optional[str] = None
    target_audience: Optional[str] = None
    language: str = "en"
    status: str = "new"  # new, ready_for_upload, completed, archived
    priority: int = 0
    source: Optional[str] = None
    source_reference: Optional[str] = None
    parent_idea_id: Optional[int] = None
    root_idea_id: Optional[int] = None
    version: int = 1
    idea_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    scheduled_for: Optional[datetime] = None
    generated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    is_deleted: int = 0


class IdeaElement(YouTubeBaseModel, table=True):
    __tablename__ = "idea_elements"

    idea_id: int = Field(foreign_key="ideas.id", primary_key=True)
    element_id: int = Field(foreign_key="elements.id", primary_key=True)
    is_primary: bool = False


class Prompt(YouTubeBaseModel, table=True):
    __tablename__ = "prompts"

    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: str = Field(index=True, unique=True)
    idea_id: int = Field(foreign_key="ideas.id", index=True)
    prompt_type: Optional[str] = None  # image_prompt, video_prompt
    title: Optional[str] = None
    prompt_text: str
    negative_prompt: Optional[str] = None
    system_instruction: Optional[str] = None
    model_target: Optional[str] = None
    generation_type: Optional[str] = None  # image, video
    aspect_ratio: Optional[str] = None
    duration_seconds: Optional[float] = None
    language: Optional[str] = "en"
    status: str = "ready"
    version: int = 1
    prompt_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    level: Optional[int] = Field(default=None, index=True)  # 1 to 10
    level_name: Optional[str] = None
    structure_type: Optional[str] = None  # 5_layer_montage, 8s_5_step_hud_popup
    reference_image_prompt_id: Optional[int] = Field(default=None, foreign_key="prompts.id")


class Task(YouTubeBaseModel, table=True):
    __tablename__ = "tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: str = Field(index=True, unique=True)
    idea_id: Optional[int] = Field(default=None, foreign_key="ideas.id", index=True)
    prompt_id: Optional[int] = Field(default=None, foreign_key="prompts.id", index=True)
    video_title: str
    task_type: str = "veo_level10_package"  # veo_level10_package, prompt_escalation, element_gen
    status: str = "pending"  # pending, running, success, failed, permanent_failure
    attempt_count: int = 0
    max_attempts: int = 3
    output_folder_path: Optional[str] = None
    video_path: Optional[str] = None
    metadata_json_path: Optional[str] = None
    last_error: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class TaskAttempt(YouTubeBaseModel, table=True):
    __tablename__ = "task_attempts"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="tasks.id", index=True)
    attempt_number: int
    status: str  # running, success, failed
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: Optional[datetime] = None


class GeneratedVideo(YouTubeBaseModel, table=True):
    __tablename__ = "generated_videos"

    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: str = Field(index=True, unique=True)
    idea_id: int = Field(foreign_key="ideas.id", index=True)
    generation_job_id: Optional[int] = None
    title: Optional[str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    file_size_bytes: Optional[int] = None
    format: Optional[str] = None
    codec: Optional[str] = None
    resolution: Optional[str] = "1080p"
    thumbnail_path: Optional[str] = None
    subtitle_path: Optional[str] = None
    audio_path: Optional[str] = None
    quality_score: Optional[float] = None
    status: Optional[str] = "completed"
    created_at: datetime = Field(default_factory=_utcnow)


class PromptingStyleMaster(YouTubeBaseModel, table=True):
    __tablename__ = "prompting_style_master"

    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: str = Field(index=True, unique=True)
    stage_name: str = Field(index=True)  # ELEMENT_GENERATION, IDEA_GENERATION, PROMPT_ESCALATION, YOUTUBE_METADATA
    target_hierarchy_level: str  # Level 1->2, Level 2->3, Level 3->4, Level 4->5
    style_title: str
    system_role: str
    system_instruction: str
    prompt_template: str
    output_format: str  # JSON_OBJECT, JSON_ARRAY, STRUCTURED_TEXT
    model_target: str  # ChatGPT-4o / Playwright, Veo, Imagen
    rules_and_constraints: str
    is_active: int = 1
    version: int = 1
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class YouTubeMetadata(YouTubeBaseModel, table=True):
    __tablename__ = "youtube_metadata"

    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: str = Field(index=True, unique=True)
    idea_id: int = Field(foreign_key="ideas.id", index=True)
    element_id: Optional[int] = Field(default=None, foreign_key="elements.id", index=True)
    title: str
    seo_description: str
    tags: str  # JSON string array of tags
    category: str = "Science & Technology"
    default_language: str = "en"
    video_prompt_used: Optional[str] = None
    image_prompt_used: Optional[str] = None
    video_file_path: Optional[str] = None
    package_folder_path: Optional[str] = None
    status: str = "ready"  # ready, uploaded, archived
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

