"""Pipeline defaults — locked values for the 9:16 / Veo 3.1 Lite / 8s workflow.

These are not config; they're hard requirements for the humanless
image-to-video automation as agreed with the user (2026-07-12):

  * Always 9:16 (mobile-first vertical; user explicitly forbade 16:9 / 1:1)
  * Always Veo 3.1 Lite (cheapest video model on Flow's paygate — ~10 credits
    for an 8s clip; full Veo 3.1 is ~30 credits per 8s and Pro plan rejects
    long-form requests anyway)
  * Always 8 seconds (single short clip; user explicitly forbade long video)
  * Always GEM_PIX_2 for image (default Flow image model — Pro plan available)

If anyone tries to override these (env var, request body, future code),
``validate_*`` raises ValueError before the request leaves the agent.
The single-shot endpoint in ``routes/automate.py`` also reads these
constants as defaults, so the user only has to send the *content*
(prompts + camera dynamic) — not the meta-choices.
"""
from __future__ import annotations

from typing import Final


# ── Locked values ───────────────────────────────────────────────────────────
DEFAULT_ASPECT_RATIO:   Final[str]  = "9:16"
DEFAULT_VIDEO_MODEL:    Final[str]  = "VEO_3_1_LITE"
DEFAULT_DURATION_S:     Final[int]  = 8
DEFAULT_IMAGE_MODEL:    Final[str]  = "GEM_PIX_2"

# Conservative cost estimate per video. Used by /api/automate/image-to-video
# to fail-fast if credits are too low instead of starting a request that
# Google will reject mid-flight.
ESTIMATED_CREDITS_PER_VIDEO: Final[int] = 10


# ── Validators ──────────────────────────────────────────────────────────────
class PipelineConfigError(ValueError):
    """Raised when a caller tries to override a locked pipeline default.

    The 9:16 / Lite / 8s rules are deliberate user requirements — a ValueError
    here means the script tried to send the wrong aspect / model / duration
    and we refused rather than silently change the workflow.
    """


def validate_aspect_ratio(aspect: str | None) -> str:
    """Accept "9:16" only. Anything else is rejected."""
    if aspect is None:
        return DEFAULT_ASPECT_RATIO
    if aspect != DEFAULT_ASPECT_RATIO:
        raise PipelineConfigError(
            f"aspect_ratio {aspect!r} not allowed. "
            f"Use {DEFAULT_ASPECT_RATIO!r} (locked for this pipeline)."
        )
    return aspect


def validate_video_model(model: str | None) -> str:
    """Accept "VEO_3_1_LITE" only. Full Veo 3.1 / Pro / Sora rejected."""
    if model is None:
        return DEFAULT_VIDEO_MODEL
    if model != DEFAULT_VIDEO_MODEL:
        raise PipelineConfigError(
            f"video_model {model!r} not allowed. "
            f"Use {DEFAULT_VIDEO_MODEL!r} (locked for this pipeline)."
        )
    return model


def validate_duration_s(duration: int | None) -> int:
    """Accept 8 only. Long video rejected."""
    if duration is None:
        return DEFAULT_DURATION_S
    if duration != DEFAULT_DURATION_S:
        raise PipelineConfigError(
            f"duration_s {duration} not allowed. "
            f"Use {DEFAULT_DURATION_S}s (locked for this pipeline)."
        )
    return duration


def validate_image_model(model: str | None) -> str:
    """Accept "GEM_PIX_2" only."""
    if model is None:
        return DEFAULT_IMAGE_MODEL
    if model != DEFAULT_IMAGE_MODEL:
        raise PipelineConfigError(
            f"image_model {model!r} not allowed. "
            f"Use {DEFAULT_IMAGE_MODEL!r} (locked for this pipeline)."
        )
    return model


def apply_pipeline_defaults(payload: dict) -> dict:
    """Mutate-and-return ``payload`` so that any unset locked field gets the
    default. Used by /api/automate/image-to-video as the entry point.

    Raises PipelineConfigError if any locked field is *explicitly* set to
    a wrong value — this is the early-warning that catches a caller trying
    to sneak in a 16:9 or full Veo request.
    """
    out = dict(payload)  # don't mutate caller's dict

    # Validate-and-default. Order matters: aspect first (cheapest), then
    # video model / duration (still cheap), then image model (cheap).
    out["aspect_ratio"] = validate_aspect_ratio(out.get("aspect_ratio"))
    out["video_model"]  = validate_video_model(out.get("video_model"))
    out["duration_s"]   = validate_duration_s(out.get("duration_s"))
    out["image_model"]  = validate_image_model(out.get("image_model"))

    return out


__all__ = [
    "DEFAULT_ASPECT_RATIO",
    "DEFAULT_VIDEO_MODEL",
    "DEFAULT_DURATION_S",
    "DEFAULT_IMAGE_MODEL",
    "ESTIMATED_CREDITS_PER_VIDEO",
    "PipelineConfigError",
    "validate_aspect_ratio",
    "validate_video_model",
    "validate_duration_s",
    "validate_image_model",
    "apply_pipeline_defaults",
]