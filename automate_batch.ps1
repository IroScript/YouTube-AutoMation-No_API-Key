<#
.SYNOPSIS
    Run multiple image-to-video jobs sequentially through the Flowboard
    /api/automate/batch endpoint.

.DESCRIPTION
    Reads a JSON file containing an array of items, each with image_prompt +
    video_prompt + camera_dynamic. Calls /api/automate/batch which runs them
    sequentially server-side (preserving token-refresh + credit guard
    semantics).

    Output: <name>.mp4 per item, saved to ./output/.

    Sequential NOT parallel: Veo 3.1 Lite on Pro plan rate-limits at ~1 video
    per 30-60s; parallel requests would 429 immediately. Server-side
    sequential means a single Bearer token stays fresh for the whole batch
    (50-min refresh window).

.PARAMETER PromptsFile
    Path to a JSON file. Schema:
    {
      "items": [
        { "image_prompt": "...", "video_prompt": "...", "camera_dynamic": "...", "name": "shot_01" },
        { "image_prompt": "...", "video_prompt": "...", "camera_dynamic": "...", "name": "shot_02" }
      ]
    }

.PARAMETER OutputDir
    Where to save MP4 files. Default: .\output.

.PARAMETER AgentUrl
    Override the agent base URL. Default: http://127.0.0.1:8101.

.EXAMPLE
    .\automate_batch.ps1 -PromptsFile .\prompts\batch_5_shots.json
    .\automate_batch.ps1 -PromptsFile .\prompts\batch.json -OutputDir D:\renders
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$PromptsFile,

    [string]$OutputDir = ".\output",

    [string]$AgentUrl = "http://127.0.0.1:8101"
)

$ErrorActionPreference = "Stop"

# ─── Preflight ─────────────────────────────────────────────────────────────
if (-not (Test-Path $PromptsFile)) {
    throw "Prompts file not found: $PromptsFile"
}

$OutputDir = (Resolve-Path -LiteralPath $OutputDir -ErrorAction SilentlyContinue)?.Path
if (-not $OutputDir) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    $OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
}

# ─── Parse prompts ─────────────────────────────────────────────────────────
$payload = Get-Content $PromptsFile -Raw | ConvertFrom-Json

if (-not $payload.items -or $payload.items.Count -eq 0) {
    throw "Prompts file missing 'items' array (need at least 1)"
}

# Auto-fill names from positional index if absent.
for ($i = 0; $i -lt $payload.items.Count; $i++) {
    $item = $payload.items[$i]
    if (-not $item.name) {
        $item | Add-Member -NotePropertyName "name" -NotePropertyValue ("shot_{0:D2}" -f ($i + 1)) -Force
    }
}

$total = $payload.items.Count
Write-Host "[automate_batch] Loaded $total items from $PromptsFile" -ForegroundColor Cyan
Write-Host "[automate_batch] Output directory: $OutputDir"
Write-Host ""

# ─── Submit batch ──────────────────────────────────────────────────────────
$submitUrl = "$AgentUrl/api/automate/batch"
$bodyJson = $payload | ConvertTo-Json -Depth 8

Write-Host "[automate_batch] Calling $submitUrl ..."
$sw = [System.Diagnostics.Stopwatch]::StartNew()

try {
    $batchResp = Invoke-RestMethod -Method POST -Uri $submitUrl -Body $bodyJson -ContentType "application/json" -TimeoutSec 1800
}
catch {
    $err = $_.Exception.Response
    if ($err) {
        $reader = New-Object System.IO.StreamReader($err.GetResponseStream())
        $body_text = $reader.ReadToEnd()
        Write-Host "[FAIL] HTTP $($err.StatusCode.Value__): $body_text" -ForegroundColor Red
    } else {
        Write-Host "[FAIL] $($_.Exception.Message)" -ForegroundColor Red
    }
    exit 1
}

$sw.Stop()
Write-Host ""
Write-Host "[automate_batch] Done in $([Math]::Round($sw.Elapsed.TotalSeconds, 1))s" -ForegroundColor Cyan
Write-Host "  Total     : $($batchResp.total)"
Write-Host "  Succeeded : $($batchResp.succeeded)"
Write-Host "  Failed    : $($batchResp.failed)"
Write-Host ""

# ─── Per-item report + download ────────────────────────────────────────────
$downloaded = 0
$failed = 0

foreach ($item in $batchResp.results) {
    $idx = $item.index
    $status = $item.status
    $name = $item.name

    if ($status -ne "done") {
        Write-Host "[$idx/$total] FAILED  : $name  →  $($item.error)" -ForegroundColor Red
        $failed++
        continue
    }

    $videoId = $item.video_media_id
    if (-not $videoId) {
        Write-Host "[$idx/$total] FAILED  : $name  (no video_media_id in response)" -ForegroundColor Red
        $failed++
        continue
    }

    $mediaUrl = "$AgentUrl$($item.mp4_url)"
    $outFile = Join-Path $OutputDir "$name.mp4"

    try {
        Invoke-WebRequest -Uri $mediaUrl -OutFile $outFile -TimeoutSec 300 -UseBasicParsing
        $sizeKB = [Math]::Round((Get-Item $outFile).Length / 1KB, 1)
        $elapsed = if ($null -ne $item.elapsed_s) { [Math]::Round($item.elapsed_s, 1) } else { "?" }
        Write-Host "[$idx/$total] OK      : $name  (${sizeKB} KB, ${elapsed}s)" -ForegroundColor Green
        $downloaded++
    }
    catch {
        Write-Host "[$idx/$total] FAILED  : $name  (download error: $($_.Exception.Message))" -ForegroundColor Red
        $failed++
    }
}

Write-Host ""
Write-Host "[automate_batch] Saved $downloaded MP4(s) to $OutputDir" -ForegroundColor Cyan
if ($failed -gt 0) {
    Write-Host "[automate_batch] $failed item(s) failed" -ForegroundColor Yellow
    exit 1
}
exit 0