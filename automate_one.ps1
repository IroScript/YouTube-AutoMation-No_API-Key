<#
.SYNOPSIS
    Run one image-to-video job through the Flowboard automate endpoint.

.DESCRIPTION
    Reads a JSON file containing image_prompt + video_prompt + camera_dynamic,
    calls POST /api/automate/image-to-video, polls the resulting MP4 URL until
    the bytes are downloadable, then saves the file to ./output/<name>.mp4.

    The Flowboard agent (uvicorn on :8101) must already be running. The
    Chrome extension on Profile 6 must be connected (token captured + tier
    resolved) — the endpoint will refuse with HTTP 503 otherwise.

    Locked pipeline (server-side, NOT overridable from this script):
      * aspect_ratio = "9:16"
      * video_model  = "VEO_3_1_LITE"
      * duration_s   = 8
      * image_model  = "GEM_PIX_2"

.PARAMETER PromptsFile
    Path to a JSON file. Schema:
    {
      "image_prompt":   "a lone astronaut on a red Martian cliff at golden hour, cinematic",
      "video_prompt":   "wind picks up dust, two moons rise",
      "camera_dynamic": "slow dolly forward + tilt up",
      "name":           "astronaut_cliff"
    }

.PARAMETER OutputDir
    Where to save the resulting MP4. Default: .\output (created if missing).

.PARAMETER AgentUrl
    Override the agent base URL. Default: http://127.0.0.1:8101.

.EXAMPLE
    .\automate_one.ps1 -PromptsFile .\prompts\astronaut.json
    .\automate_one.ps1 -PromptsFile .\prompts\astronaut.json -OutputDir D:\renders
#>
param(
    [string]$PromptsFile = ".\prompts\mystic_floating_island.json",

    [string]$OutputDir = ".\output",

    [string]$AgentUrl = "http://127.0.0.1:8101"
)

$ErrorActionPreference = "Stop"

# ─── Preflight ─────────────────────────────────────────────────────────────
if (-not (Test-Path $PromptsFile)) {
    throw "Prompts file not found: $PromptsFile"
}

# Resolve output dir relative to current working dir, NOT the script dir,
# because the user typically cd's into a project folder and runs from there.
$resolved = Resolve-Path -LiteralPath $OutputDir -ErrorAction SilentlyContinue
if ($resolved) {
    $OutputDir = $resolved.Path
} else {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    $OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
}

# ─── Parse prompts ─────────────────────────────────────────────────────────
$prompts = Get-Content $PromptsFile -Raw | ConvertFrom-Json

if (-not $prompts.image_prompt) { throw "Prompts file missing required field: image_prompt" }
if (-not $prompts.video_prompt) { throw "Prompts file missing required field: video_prompt" }

# Default name = file stem, or uuid if absent.
if ($prompts.name) {
    $name = $prompts.name
} else {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($PromptsFile)
}

# ─── Build request body ───────────────────────────────────────────────────
# Camera dynamic is optional; we pass it through if the user supplied one.
$body = @{
    image_prompt   = $prompts.image_prompt
    video_prompt   = $prompts.video_prompt
    camera_dynamic = $prompts.camera_dynamic
    name           = $name
}
$bodyJson = $body | ConvertTo-Json -Depth 5 -Compress

Write-Host "[automate_one] Submitting job: $name" -ForegroundColor Cyan
Write-Host "  image_prompt   : $($prompts.image_prompt.Substring(0, [Math]::Min(80, $prompts.image_prompt.Length)))..."
Write-Host "  video_prompt   : $($prompts.video_prompt.Substring(0, [Math]::Min(80, $prompts.video_prompt.Length)))..."
if ($prompts.camera_dynamic) {
    Write-Host "  camera_dynamic : $($prompts.camera_dynamic)"
}
Write-Host "[automate_one] Request sent to server. Generating image & 8-second Veo video..." -ForegroundColor Yellow
Write-Host "              Please wait ~60-120 seconds for completion..." -ForegroundColor DarkYellow
Write-Host ""

# ─── Call endpoint ────────────────────────────────────────────────────────
$submitUrl = "$AgentUrl/api/automate/image-to-video"
try {
    $response = Invoke-RestMethod -Method POST -Uri $submitUrl -Body $bodyJson -ContentType "application/json" -TimeoutSec 600
}
catch {
    $statusCode = ""
    $body_text = ""
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
        $body_text = $_.ErrorDetails.Message
    }
    if ($_.Exception -and $_.Exception.Response) {
        $resp = $_.Exception.Response
        try {
            if ($resp.StatusCode) {
                $statusCode = [int]$resp.StatusCode
            }
        } catch {}
        if (-not $body_text) {
            try {
                if ($resp.Content -and $resp.Content.ReadAsStringAsync) {
                    $body_text = $resp.Content.ReadAsStringAsync().Result
                } elseif ($resp.GetType().GetMethod("GetResponseStream")) {
                    $stream = $resp.GetResponseStream()
                    if ($stream) {
                        $reader = New-Object System.IO.StreamReader($stream)
                        $body_text = $reader.ReadToEnd()
                    }
                }
            } catch {}
        }
    }
    if (-not $body_text) {
        $body_text = $_.Exception.Message
    }
    if ($statusCode) {
        Write-Host "[FAIL] HTTP ${statusCode}: $body_text" -ForegroundColor Red
    } else {
        Write-Host "[FAIL] $body_text" -ForegroundColor Red
    }
    if ($statusCode -eq 503 -or $body_text -like "*Extension is not connected*") {
        Write-Host ""
        Write-Host "[TIP] Chrome Extension is not connected or Token is missing." -ForegroundColor Yellow
        Write-Host "      Please run: .\start_everything_and_generate.ps1 -PromptsFile $PromptsFile" -ForegroundColor Cyan
    }
    exit 1
}

# ─── Verify response ───────────────────────────────────────────────────────
if (-not $response.video_media_id) {
    Write-Host "[FAIL] Endpoint returned no video_media_id. Response:" -ForegroundColor Red
    $response | ConvertTo-Json -Depth 5 | Write-Host
    exit 1
}

Write-Host "[automate_one] Generation succeeded." -ForegroundColor Green
Write-Host "  image_media_id : $($response.image_media_id)"
Write-Host "  video_media_id : $($response.video_media_id)"
Write-Host "  mp4_url        : $($response.mp4_url)"
Write-Host "  duration_s     : $($response.duration_s)  (locked: 8)"
Write-Host "  aspect_ratio   : $($response.aspect_ratio)  (locked: 9:16)"
Write-Host "  video_model    : $($response.video_model)  (locked: VEO_3_1_LITE)"
Write-Host "  elapsed_s      : $($response.elapsed_s)"
if ($null -ne $response.credits_remaining) {
    Write-Host "  credits_left   : $($response.credits_remaining)"
}
Write-Host ""

# ─── Download MP4 ─────────────────────────────────────────────────────────
$mediaUrl = "$AgentUrl$($response.mp4_url)"
$outFile = Join-Path $OutputDir "$name.mp4"
Write-Host "[automate_one] Downloading to: $outFile"
try {
    Invoke-WebRequest -Uri $mediaUrl -OutFile $outFile -TimeoutSec 300 -UseBasicParsing
}
catch {
    Write-Host "[FAIL] Download failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

$sizeBytes = (Get-Item $outFile).Length
Write-Host "[automate_one] Saved $([Math]::Round($sizeBytes / 1KB, 1)) KB" -ForegroundColor Green
Write-Host ""
exit 0