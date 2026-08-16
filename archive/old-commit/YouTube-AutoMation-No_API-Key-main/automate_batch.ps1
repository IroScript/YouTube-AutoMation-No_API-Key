<#
.SYNOPSIS
    Run multiple image-to-video jobs sequentially through the Flowboard
    /api/automate/batch endpoint with full autonomous startup.

.DESCRIPTION
    1. Checks if Agent (:8101) is running; starts it automatically if not.
    2. Checks if Frontend (:5173) is running; starts it automatically if not.
    3. Launches Chrome Profile 4 with Google Flow & Flowboard UI if needed.
    4. Waits for Extension connection + Token + Paygate Tier to settle.
    5. Reads batch JSON file, submits batch to server, downloads MP4s to ./output/.

.PARAMETER PromptsFile
    Path to a JSON file containing items array. Default: .\prompts\batch_3.json

.PARAMETER OutputDir
    Where to save MP4 files. Default: .\output.

.PARAMETER AgentUrl
    Override the agent base URL. Default: http://127.0.0.1:8101.

.PARAMETER VerifyOnly
    If set, only checks readiness without launching video generation.

.EXAMPLE
    .\automate_batch.ps1 -PromptsFile .\prompts\batch_3.json
#>
param(
    [string]$PromptsFile = ".\prompts\batch_3.json",

    [string]$OutputDir = ".\output",

    [string]$AgentUrl = "http://127.0.0.1:8101",

    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

# ─── 0. Autonomous Environment Startup & Readiness Checks ─────────────────
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " MASTER AUTONOMOUS FLOWBOARD BATCH RUNNER (automate_batch)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Check if agent is listening on :8101 ---
$agentHealthUrl = "$AgentUrl/api/health"
$agentRunning = $false
$initialHealth = $null
try {
    $initialHealth = Invoke-RestMethod -Uri $agentHealthUrl -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($initialHealth.ok) {
        $agentRunning = $true
    }
} catch {}

if (-not $agentRunning) {
    Write-Host "[1/4] Starting Flowboard Agent on :8101..." -ForegroundColor Yellow
    $agentDir = Join-Path $RepoRoot "flowboard\agent"
    $pythonExe = Join-Path $agentDir ".venv\Scripts\python.exe"

    if (-not (Test-Path $pythonExe)) {
        Write-Host "[FAIL] Python venv not found at $pythonExe" -ForegroundColor Red
        exit 1
    }

    Start-Process -FilePath $pythonExe -ArgumentList "-m uvicorn flowboard.main:app --port 8101" -WorkingDirectory $agentDir -WindowStyle Hidden
    Write-Host "      Waiting for agent to initialize..."
    for ($i = 1; $i -le 15; $i++) {
        Start-Sleep -Seconds 1
        try {
            $initialHealth = Invoke-RestMethod -Uri $agentHealthUrl -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($initialHealth.ok) {
                $agentRunning = $true
                Write-Host "      [OK] Agent is up and running! ($i s)" -ForegroundColor Green
                break
            }
        } catch {}
    }
    if (-not $agentRunning) {
        Write-Host "[FAIL] Agent server failed to respond on :8101 within 15s." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[1/4] Flowboard Agent is already running on :8101." -ForegroundColor Green
}

# --- 1b. Check if Frontend is running on :5173 ---
$feUrl = "http://localhost:5173/"
$feRunning = $false
try {
    $feStatus = (Invoke-WebRequest -Uri $feUrl -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue).StatusCode
    if ($feStatus -eq 200) { $feRunning = $true }
} catch {}

if (-not $feRunning) {
    Write-Host "[1b/4] Starting Flowboard Frontend (Vite on :5173)..." -ForegroundColor Yellow
    $frontendDir = Join-Path $RepoRoot "flowboard\frontend"
    Start-Process "cmd.exe" -ArgumentList "/c cd /d `"$frontendDir`" && npm run dev" -WindowStyle Hidden
} else {
    Write-Host "[1b/4] Flowboard Frontend is already running on :5173." -ForegroundColor Green
}

# --- 2. Check and Launch Chrome if extension/token not already ready ---
$alreadyReady = $false
if ($initialHealth) {
    $extConn = $initialHealth.extension_connected
    $hasKey = $false
    if ($initialHealth.ws_stats) {
        $hasKey = [bool]$initialHealth.ws_stats.flow_key_present
    }
    if ($extConn -and $hasKey) {
        try {
            $me = Invoke-RestMethod -Uri "$AgentUrl/api/auth/me" -TimeoutSec 3 -ErrorAction SilentlyContinue
            if ($me.paygate_tier) {
                $alreadyReady = $true
            }
        } catch {}
    }
}

if ($alreadyReady) {
    Write-Host "[2/4] Chrome Extension, Token and Tier are ALREADY ready." -ForegroundColor Green
} else {
    $targetProfile = "Profile 4"
    try {
        $runningCmds = (Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" -ErrorAction SilentlyContinue).CommandLine
        $runningProfiles = @()
        foreach ($cmd in $runningCmds) {
            if ($cmd -match '--profile-directory="([^"]+)"') {
                $runningProfiles += $Matches[1]
            }
        }
        $runningProfiles = $runningProfiles | Select-Object -Unique

        $userDataDir = "$env:LOCALAPPDATA\Google\Chrome\User Data"
        $matchingProfiles = @()
        if (Test-Path $userDataDir) {
            $prefFiles = Get-ChildItem -Path $userDataDir -Filter "Preferences" -Recurse -ErrorAction SilentlyContinue
            foreach ($pref in $prefFiles) {
                $content = Get-Content $pref.FullName -Raw -ErrorAction SilentlyContinue
                if ($content -like "*flowboard*") {
                    $matchingProfiles += $pref.Directory.Name
                }
            }
        }

        if ($matchingProfiles) {
            $runningMatch = $matchingProfiles | Where-Object { $runningProfiles -contains $_ } | Select-Object -First 1
            if ($runningMatch) {
                $targetProfile = $runningMatch
            } else {
                $targetProfile = $matchingProfiles[0]
            }
        } elseif ($runningProfiles) {
            $targetProfile = $runningProfiles[0]
        }
    } catch {}

    Write-Host "[2/4] Launching Chrome ($targetProfile) to Flowboard UI (localhost:5173) and Google Flow..." -ForegroundColor Yellow
    try {
        Start-Process "chrome.exe" -ArgumentList "--profile-directory=`"$targetProfile`" --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding http://localhost:5173/ https://labs.google/fx/tools/flow"
    } catch {
        Write-Host "      [WARN] Could not launch chrome.exe directly: $_" -ForegroundColor Red
    }
}

# --- 3. Wait for Extension + Token + Paygate Tier (Active Poll Loop) ---
Write-Host "[3/4] Checking Chrome Extension, Token and Tier status..." -ForegroundColor Yellow
$ready = $false
$maxAttempts = 45  # 90 seconds total

try {
    $pf = Invoke-RestMethod -Uri $agentHealthUrl -TimeoutSec 2 -ErrorAction SilentlyContinue
    $pfKey = $false
    if ($pf.ws_stats) { $pfKey = [bool]$pf.ws_stats.flow_key_present }
    if ($pf.extension_connected -and $pfKey) {
        $pfMe = Invoke-RestMethod -Uri "$AgentUrl/api/auth/me" -TimeoutSec 3 -ErrorAction SilentlyContinue
        if ($pfMe.paygate_tier) {
            $ready = $true
            $me = $pfMe
            Write-Host "      [OK] All 3 Readiness Checks Passed! (pre-flight)" -ForegroundColor Green
            Write-Host "         [OK 1/3] Extension Connected via WS (:9223)" -ForegroundColor Green
            Write-Host "         [OK 2/3] Bearer Token Captured" -ForegroundColor Green
            Write-Host "         [OK 3/3] Paygate Tier Resolved ($($me.paygate_tier))" -ForegroundColor Green
            Write-Host "         Email:   $($me.email)" -ForegroundColor Gray
            Write-Host "         SKU:     $($me.sku)" -ForegroundColor Gray
            if ($null -ne $me.credits) {
                Write-Host "         Credits: $($me.credits)" -ForegroundColor Gray
            }
        }
    }
} catch {}

for ($attempt = 1; $attempt -le $maxAttempts -and -not $ready; $attempt++) {
    try {
        try {
            Invoke-RestMethod -Method POST -Uri "$AgentUrl/api/auth/scan" -TimeoutSec 3 -ErrorAction SilentlyContinue | Out-Null
        } catch {}

        if ($attempt -eq 20) {
            Write-Host "      [RETRY] Attempting force_recapture for fresh token..." -ForegroundColor DarkYellow
            try {
                Invoke-RestMethod -Method POST -Uri "$AgentUrl/api/auth/scan" -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null
            } catch {}
        }

        $health = Invoke-RestMethod -Uri $agentHealthUrl -TimeoutSec 2 -ErrorAction SilentlyContinue
        $hasKey = $false
        if ($health.ws_stats) {
            $hasKey = [bool]$health.ws_stats.flow_key_present
        }
        $extConn = [bool]$health.extension_connected

        $hasTier = $false
        if ($extConn -and $hasKey) {
            try {
                $me = Invoke-RestMethod -Uri "$AgentUrl/api/auth/me" -TimeoutSec 3 -ErrorAction SilentlyContinue
                if ($me.paygate_tier) {
                    $hasTier = $true
                }
            } catch {}
        }

        if ($extConn -and $hasKey -and $hasTier) {
            $ready = $true
            Write-Host "      [OK] All 3 Readiness Checks Passed!" -ForegroundColor Green
            Write-Host "         [OK 1/3] Extension Connected via WS (:9223)" -ForegroundColor Green
            Write-Host "         [OK 2/3] Bearer Token Captured" -ForegroundColor Green
            Write-Host "         [OK 3/3] Paygate Tier Resolved ($($me.paygate_tier))" -ForegroundColor Green
            Write-Host "         Email:   $($me.email)" -ForegroundColor Gray
            Write-Host "         SKU:     $($me.sku)" -ForegroundColor Gray
            if ($null -ne $me.credits) {
                Write-Host "         Credits: $($me.credits)" -ForegroundColor Gray
            }
            break
        } elseif ($extConn -and $hasKey) {
            Write-Host "      [WAIT] Token captured, resolving paygate tier... (attempt $attempt/$maxAttempts)" -ForegroundColor Yellow
        } elseif ($extConn) {
            Write-Host "      [WAIT] Extension connected, waiting for Bearer token... (attempt $attempt/$maxAttempts)" -ForegroundColor Yellow
            Write-Host "         NOTE: Token only appears when Flow page has an active Sign-In session." -ForegroundColor DarkYellow
        } else {
            Write-Host "      [WAIT] Waiting for Chrome Extension to connect via WS:9223... (attempt $attempt/$maxAttempts)" -ForegroundColor Gray
        }
    } catch {}
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    Write-Host ""
    Write-Host "      -------------------------------------------------------------" -ForegroundColor Red
    Write-Host "      READINESS CHECK FAILED after $($maxAttempts * 2) seconds" -ForegroundColor Red
    Write-Host "" -ForegroundColor Red

    $diagExt = $false; $diagKey = $false; $diagTier = $false
    try {
        $dh = Invoke-RestMethod -Uri $agentHealthUrl -TimeoutSec 2 -ErrorAction SilentlyContinue
        $diagExt = [bool]$dh.extension_connected
        if ($dh.ws_stats) { $diagKey = [bool]$dh.ws_stats.flow_key_present }
        if ($diagExt -and $diagKey) {
            $dm = Invoke-RestMethod -Uri "$AgentUrl/api/auth/me" -TimeoutSec 3 -ErrorAction SilentlyContinue
            if ($dm.paygate_tier) { $diagTier = $true }
        }
    } catch {}

    Write-Host "      Diagnostic:" -ForegroundColor Red
    if ($diagExt) {
        Write-Host "        [OK] 1/3 Extension Connected via WS (:9223)" -ForegroundColor Green
    } else {
        Write-Host "        [FAIL] 1/3 Extension NOT connected" -ForegroundColor Red
        Write-Host "          -> Install Flowboard Bridge in Profile 4: run install_extension.bat" -ForegroundColor Gray
        Write-Host "          -> Then load it via chrome://extensions (Load unpacked)" -ForegroundColor Gray
    }
    if ($diagKey) {
        Write-Host "        [OK] 2/3 Bearer Token Captured" -ForegroundColor Green
    } else {
        Write-Host "        [FAIL] 2/3 Bearer Token NOT captured" -ForegroundColor Red
        Write-Host "          -> Open labs.google/fx/tools/flow in Profile 4 and SIGN IN" -ForegroundColor Gray
    }
    if ($diagTier) {
        Write-Host "        [OK] 3/3 Paygate Tier Resolved" -ForegroundColor Green
    } else {
        Write-Host "        [FAIL] 3/3 Paygate Tier NOT resolved" -ForegroundColor Red
        Write-Host "          -> Token may be expired or Google session is invalid" -ForegroundColor Gray
        Write-Host "          -> Refresh the Flow page (Ctrl+R) and wait 10s, then retry" -ForegroundColor Gray
    }
    Write-Host "      -------------------------------------------------------------" -ForegroundColor Red
    Write-Host ""
    exit 1
}

if ($VerifyOnly) {
    Write-Host ""
    Write-Host "[4/4] VERIFY ONLY MODE - System is READY for batch video generation!" -ForegroundColor Green
    Write-Host "      Run without -VerifyOnly to start generating." -ForegroundColor Gray
    exit 0
}

# ─── 4. Preflight & Prompts Resolution ─────────────────────────────────────
if (-not (Test-Path $PromptsFile)) {
    throw "Prompts file not found: $PromptsFile"
}

$resolved = Resolve-Path -LiteralPath $OutputDir -ErrorAction SilentlyContinue
if ($resolved) {
    $OutputDir = $resolved.Path
} else {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    $OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
}

# ─── Parse prompts ─────────────────────────────────────────────────────────
$payload = Get-Content $PromptsFile -Raw | ConvertFrom-Json

if (-not $payload.items -or $payload.items.Count -eq 0) {
    throw "Prompts file missing 'items' array (need at least 1)"
}

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
        Write-Host "      Please check Profile 4 Flow tab." -ForegroundColor Cyan
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