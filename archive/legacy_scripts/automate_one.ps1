<#
.SYNOPSIS
    All-in-one autonomous runner for Flowboard image-to-video generation.

.DESCRIPTION
    1. Checks if Agent (:8101) is running; starts it automatically if not.
    2. Checks if Frontend (:5173) is running; starts it automatically if not.
    3. Launches Chrome Profile 4 with Google Flow & Flowboard UI if needed.
    4. Waits for Extension connection + Token + Paygate Tier to settle.
    5. Reads prompt JSON file (image_prompt + video_prompt + camera_dynamic).
    6. Calls POST /api/automate/image-to-video, polls MP4 URL, downloads & saves to ./output/<name>.mp4.

.PARAMETER PromptsFile
    Path to a JSON file. Default: .\prompts\mystic_floating_island.json

.PARAMETER OutputDir
    Where to save the resulting MP4. Default: .\output.

.PARAMETER AgentUrl
    Override the agent base URL. Default: http://127.0.0.1:8101.

.PARAMETER VerifyOnly
    If set, only checks readiness without launching video generation.

.EXAMPLE
    .\automate_one.ps1
    .\automate_one.ps1 -PromptsFile .\prompts\my_new_prompt.json
    .\automate_one.ps1 -VerifyOnly
#>
param(
    [string]$PromptsFile = "",

    [string]$OutputDir = ".\output",

    [string]$AgentUrl = "http://127.0.0.1:8101",

    [switch]$VerifyOnly,

    [switch]$UseSqlite,

    [switch]$UseCloakBrowser
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

# ─── 0. Autonomous Environment Startup & Readiness Checks ─────────────────
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " MASTER AUTONOMOUS FLOWBOARD VIDEO RUNNER (automate_one)" -ForegroundColor Cyan
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
    # Lock strictly to Chrome Profile 4
    $targetProfile = "Profile 4"

    # ─── CloakBrowser Integration ───
    $cloakBinaryPath = "$env:USERPROFILE\.cloakbrowser\chromium-146.0.7680.177.5\chrome.exe"
    $usingCloak = $false

    if ($UseCloakBrowser -and (Test-Path $cloakBinaryPath)) {
        $chromePath = $cloakBinaryPath
        $usingCloak = $true
        Write-Host "      [CLOAK] CloakBrowser binary found: $cloakBinaryPath" -ForegroundColor Magenta
    } else {
        if ($UseCloakBrowser) {
            Write-Host "      [WARN] CloakBrowser binary not found at $cloakBinaryPath, falling back to Chrome" -ForegroundColor Red
        }
        $chromePath = "chrome.exe"
        $knownPaths = @(
            "C:\Program Files\Google\Chrome\Application\chrome.exe",
            "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
        )
        foreach ($p in $knownPaths) {
            if (Test-Path $p) {
                $chromePath = $p
                break
            }
        }
    }

    # ─── Build launch arguments ───
    $chromeUserDataDir = "$env:LOCALAPPDATA\Google\Chrome\User Data"
    $baseArgs = "--profile-directory=`"$targetProfile`" --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding"

    if ($usingCloak) {
        # CloakBrowser needs explicit user-data-dir, extension loading, and stealth fingerprint args
        $extensionDir = "$RepoRoot\flowboard\extension"
        $baseArgs = "--user-data-dir=`"$chromeUserDataDir`" $baseArgs --fingerprint=48265 --fingerprint-platform=windows --enable-extensions --load-extension=`"$extensionDir`""
        Write-Host "[2/4] Launching CloakBrowser ($targetProfile) with stealth fingerprint + Flowboard extension..." -ForegroundColor Magenta
        Write-Host "      [CLOAK] Extension: $extensionDir" -ForegroundColor Magenta
    } else {
        Write-Host "[2/4] Launching Chrome ($targetProfile) to Flowboard UI (localhost:5173) and Google Flow..." -ForegroundColor Yellow
    }

    try {
        Start-Process -FilePath $chromePath -ArgumentList "$baseArgs http://localhost:5173/ https://labs.google/fx/tools/flow"
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
            if (-not $alreadyReady) {
                Write-Host "      [WARMUP] Chrome page initialized. Pausing 4s for browser scripts to settle..." -ForegroundColor Yellow
                Start-Sleep -Seconds 4
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
    Write-Host "[4/4] VERIFY ONLY MODE - System is READY for video generation!" -ForegroundColor Green
    Write-Host "      Run without -VerifyOnly to start generating." -ForegroundColor Gray
    exit 0
}

# ─── 4. Preflight & Prompts Resolution ─────────────────────────────────────
$pythonVenv = Join-Path $RepoRoot "flowboard\agent\.venv\Scripts\python.exe"
$sqliteHelper = Join-Path $RepoRoot "flowboard\agent\flowboard\sqlite_pipeline_helper.py"

if ($UseSqlite -or [string]::IsNullOrWhiteSpace($PromptsFile) -or -not (Test-Path $PromptsFile)) {
    Write-Host "[4/4] Connecting to SQLite (youtube_pipeline.db) for dynamic prompt resolution..." -ForegroundColor Cyan
    $activePromptJson = Join-Path $RepoRoot "prompts\active_sqlite_prompt.json"
    if (Test-Path $pythonVenv) {
        & $pythonVenv $sqliteHelper fetch $activePromptJson
        $PromptsFile = $activePromptJson
    } else {
        Write-Host "[WARN] Python venv not found at $pythonVenv, falling back to static prompt if available." -ForegroundColor Yellow
    }
}

if (-not (Test-Path $PromptsFile)) {
    throw "Prompts file not found or could not be generated from SQLite: $PromptsFile"
}

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

if ($prompts.name) {
    $name = $prompts.name
} else {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($PromptsFile)
}

# ─── Build request body ───────────────────────────────────────────────────
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

# ─── Call endpoint with Live Progress ─────────────────────────────────────
$asyncSubmitUrl = "$AgentUrl/api/automate/submit-async"
$syncSubmitUrl  = "$AgentUrl/api/automate/image-to-video"
$response = $null

try {
    $subResp = Invoke-RestMethod -Method POST -Uri $asyncSubmitUrl -Body $bodyJson -ContentType "application/json" -TimeoutSec 15
    $jobId = $subResp.job_id

    if ($jobId) {
        Write-Host "[automate_one] Job submitted successfully (ID: $jobId). Monitoring live progress..." -ForegroundColor Green
        $statusUrl = "$AgentUrl/api/automate/status/$jobId"
        $lastStageMsg = ""

        while ($true) {
            Start-Sleep -Seconds 1
            try {
                $st = Invoke-RestMethod -Uri $statusUrl -TimeoutSec 5 -ErrorAction SilentlyContinue
                if ($st) {
                    $pct = [int]$st.progress_pct
                    $elapsed = [Math]::Round([double]$st.elapsed_s, 1)
                    $msg = $st.stage_message

                    # Draw a 25-char progress bar
                    $barLen = 25
                    $filled = [Math]::Min($barLen, [Math]::Max(0, [int](($pct / 100.0) * $barLen)))
                    $empty = $barLen - $filled
                    $bar = ("=" * $filled) + ("-" * $empty)

                    $display = "      [$bar] $($pct.ToString().PadLeft(3))% (${elapsed}s) $msg"
                    Write-Progress -Activity "Flowboard Video Generator ($name)" -Status "$msg" -PercentComplete $pct
                    Write-Host -NoNewline ("`r$display".PadRight(110)) -ForegroundColor Yellow

                    if ($st.status -eq "completed") {
                        $response = $st.result
                        Write-Progress -Activity "Flowboard Video Generator ($name)" -Completed
                        $finalDisplay = "      [=========================] 100% ($($st.elapsed_s)s) Video generated successfully!"
                        Write-Host ("`r$finalDisplay".PadRight(110)) -ForegroundColor Green
                        Write-Host ""
                        break
                    }
                    if ($st.status -eq "failed") {
                        Write-Progress -Activity "Flowboard Video Generator ($name)" -Completed
                        Write-Host ""
                        Write-Host "[FAIL] Job failed: $($st.error)" -ForegroundColor Red
                        exit 1
                    }
                }
            } catch {}
        }
    }
} catch {
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

if ($prompts.idea_id) {
    Write-Host "[automate_one] Updating SQLite (youtube_pipeline.db) for Idea #$($prompts.idea_id)..." -ForegroundColor Cyan
    if (Test-Path $pythonVenv) {
        & $pythonVenv $sqliteHelper complete $($prompts.idea_id) "$outFile"
    }
}

Write-Host ""
exit 0