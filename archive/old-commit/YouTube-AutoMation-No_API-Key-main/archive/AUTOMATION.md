# 🎬 Humanless Image→Video Automation

**Single-call, batch-capable automation for 9:16 / Veo 3.1 Lite / 8s clips.**

> Scope: 8-second single-shot vertical videos only. Aspect 9:16, model locked
> to Veo 3.1 Lite, image model locked to GEM_PIX_2. ~10 credits per video.

---

## Architecture (1 diagram)

```
automate_one.ps1
    │
    ▼
POST /api/automate/image-to-video   ← Flowboard Agent (:8101)
    │
    ├─ apply_pipeline_defaults()    ← locks 9:16/Lite/8s/GEM_PIX_2
    ├─ token_scheduler.ensure_fresh()  ← Bearer token age check (50min)
    ├─ _handle_gen_image  (GEM_PIX_2, 9:16)
    ├─ _handle_gen_video  (Veo 3.1 Lite, 8s, 9:16, image→video)
    │
    ▼
mp4_url → /media/<id>  ← downloaded by automate_one.ps1 → ./output/<name>.mp4
```

Every Flowboard Request is also recorded so the existing UI shows the run.

---

## Prereqs (one-time)

1. **Flowboard Agent running** on `:8101`. Double-click `start_flowboard.bat`.
2. **Chrome extension connected** to Profile 6 with Flow logged in
   (`install_extension.bat` if not loaded yet). Confirm via
   `curl http://127.0.0.1:8101/api/health` → `extension_connected: true`.
3. **Pro plan tier resolved**: open the Flow tab once. AccountPanel should
   show "Pro" / credits balance.

---

## Run a single video (manual-equivalent: 8 UI steps → 1 API call)

Create a prompts file (`prompts/astronaut_cliff.json` already exists):

```json
{
  "image_prompt":   "a lone astronaut on a red Martian cliff at golden hour",
  "video_prompt":   "wind picks up dust, one moon rises above the horizon",
  "camera_dynamic": "slow dolly forward + tilt up",
  "name":           "astronaut_cliff"
}
```

Then:

```powershell
.\automate_one.ps1 -PromptsFile .\prompts\astronaut_cliff.json
```

Result:

```
[automate_one] Generation succeeded.
  image_media_id : <uuid>
  video_media_id : <uuid>
  mp4_url        : /media/<uuid>
  duration_s     : 8
  aspect_ratio   : 9:16
  video_model    : VEO_3_1_LITE
  elapsed_s      : 87.4
  credits_left   : 735
[automate_one] Saved 1245.7 KB
```

The MP4 lands in `./output/<name>.mp4`.

---

## Run a batch (3 videos overnight-style)

Create `prompts/batch.json`:

```json
{
  "items": [
    { "image_prompt": "...", "video_prompt": "...", "camera_dynamic": "...", "name": "shot_01" },
    { "image_prompt": "...", "video_prompt": "...", "camera_dynamic": "...", "name": "shot_02" }
  ]
}
```

(`prompts/batch_3.json` has a ready example.)

```powershell
.\automate_batch.ps1 -PromptsFile .\prompts\batch_3.json
```

Sequential (NOT parallel) — Veo 3.1 Lite on Pro rate-limits ~1/30-60s.

---

## What "humanless" means here

| Step | Manual in UI | Automated via endpoint |
|---|---|---|
| 1. Image node | Drag node, configure | Server creates project + runs gen_image |
| 2. Image prompt | Type into node | Sent in `image_prompt` field |
| 3. Image generated | Click Generate, wait | Poll loop in `_handle_gen_image` |
| 4. Video node | Drag node | Server runs gen_video with image as start |
| 5. Connect edge | Drag from image→video | Server threads `start_media_id` automatically |
| 6. Video prompt | Type into node | `camera_dynamic` + `video_prompt` joined |
| 7. Video generated | Click Generate, wait | `_handle_gen_video` polls until MP4 ready |
| 8. Save MP4 | Click download | `automate_one.ps1` HTTPs `/media/<id>` |

No UI interaction, no browser clicks, no Flow tab focus (except the
extension's background token-capture).

---

## Resilience

| Failure mode | Behavior |
|---|---|
| Extension disconnected | HTTP 503 with hint to reload extension |
| Token expired mid-batch | `token_scheduler.ensure_fresh()` re-captures via extension (15s) |
| Insufficient credits (<10 left) | HTTP 402 before any generation |
| Google 4xx (other) | Bubbles up as HTTP 502 with the error code |
| Stuck video render | Hard timeout in `_handle_gen_video` (5 min default) |

The token refresh check (50 min threshold) is the only piece the user
doesn't see — it runs silently before each request. If you watch the
agent log, you'll see lines like:

```
[INFO] TokenScheduler: token age 3124.5s exceeds 3000s — forcing recapture
[INFO] TokenScheduler: fresh token captured, age 1.2s
```

---

## Reference: API schema

`POST /api/automate/image-to-video`

Request body:
```json
{
  "image_prompt":   "<required>",
  "video_prompt":   "<required>",
  "camera_dynamic": "<optional>",
  "name":           "<optional, defaults to uuid>",
  "aspect_ratio":   "9:16   (locked — rejected if anything else)",
  "video_model":    "VEO_3_1_LITE  (locked)",
  "duration_s":     8     (locked)",
  "image_model":    "GEM_PIX_2  (locked)"
}
```

Response (`200`):
```json
{
  "image_media_id":     "<uuid>",
  "video_media_id":     "<uuid>",
  "mp4_url":            "/media/<uuid>",
  "image_request_id":   1234,
  "video_request_id":   1235,
  "image_project_id":   "<hex>",
  "video_project_id":   "<hex>",
  "credits_remaining":  735,
  "duration_s":         8,
  "aspect_ratio":       "9:16",
  "video_model":        "VEO_3_1_LITE",
  "elapsed_s":          87.4,
  "name":               "astronaut_cliff"
}
```

`POST /api/automate/batch`

Request body:
```json
{
  "items": [ { /* same shape as one-shot */ }, ... ]
}
```

Response:
```json
{
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "results": [
    { "index": 0, "status": "done", "name": "shot_01", "video_media_id": "...", "mp4_url": "..." },
    { "index": 1, "status": "failed", "name": "shot_02", "error": "...", "http_status": 502 }
  ]
}
```

---

## Cost & rate-limit reference

| Aspect | Value |
|---|---|
| Credits per 8s clip (Veo 3.1 Lite) | ~10 |
| Image gen (GEM_PIX_2, 9:16) | ~2 |
| **Total per pipeline run** | **~12 credits** |
| Max videos from 745 credits | ~62 |
| Sequential time per item | ~90-120s (image 10-30s + video 60-90s) |
| Token refresh window | 50 min (10 min margin under Google's 1h expiry) |
| Max items in single batch call | 50 |

If you run a batch of 50, expect ~75-100 minutes wall time. Token refresh
will fire at most once (around item 30-35 if render times are slow).