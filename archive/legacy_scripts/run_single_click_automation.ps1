<#
.SYNOPSIS
    Single-Click Autonomous Flowboard & SQLite Video Generator Runner
.DESCRIPTION
    1. Connects to SQLite (youtube_pipeline.db) to automatically fetch the next pending Idea & Level 10 prompts.
    2. Runs automate_one.ps1 to execute Agent, Frontend, Chrome Extension, and Google Flow (Veo 3.1) video generation.
    3. Downloads the generated MP4 file to .\output.
    4. Updates SQLite tables (ideas, generated_videos, 20-stage audits to TICK ✅).
#>

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Green
Write-Host " FLOWBOARD SINGLE-CLICK AUTONOMOUS VIDEO GENERATOR (SQLITE) " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

$automateScript = Join-Path $ScriptDir "automate_one.ps1"

if (-not (Test-Path $automateScript)) {
    Write-Host "[FAIL] Master script automate_one.ps1 not found at $automateScript" -ForegroundColor Red
    exit 1
}

# Run automate_one.ps1 with -UseSqlite parameter
& powershell.exe -ExecutionPolicy Bypass -File $automateScript -UseSqlite

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " [SUCCESS] SINGLE-CLICK VIDEO GENERATION COMPLETED! " -ForegroundColor Green
    Write-Host " SQLite Status: TICK (✅) | Video Saved in .\output " -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[FAIL] Single-click automation process exited with code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}
