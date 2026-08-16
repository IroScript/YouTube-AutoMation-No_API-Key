<#
.SYNOPSIS
    Master autonomous runner for Flowboard video generation.

.DESCRIPTION
    1. Checks if Agent (:8101) is running; starts it automatically if not.
    2. Launches Chrome Profile 4 with Google Flow.
    3. Waits for Extension connection + Token + Paygate Tier to settle.
    4. Runs automated video generation.

.PARAMETER PromptsFile
    Path to the prompt JSON file. Default: .\prompts\mystic_floating_island.json

.PARAMETER VerifyOnly
    If set, only checks readiness (agent + extension + token + tier) without
    launching video generation. Useful for testing after sign-in.
#>
param(
    [string]$PromptsFile = ".\prompts\mystic_floating_island.json",
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " MASTER AUTONOMOUS FLOWBOARD VIDEO RUNNER" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Check if agent is listening on :8101 ---
$agentHealthUrl = "http://127.0.0.1:8101/api/health"
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
            $me = Invoke-RestMethod -Uri "http://127.0.0.1:8101/api/auth/me" -TimeoutSec 3 -ErrorAction SilentlyContinue
            if ($me.paygate_tier) {
                $alreadyReady = $true
            }
        } catch {}
    }
}

if ($alreadyReady) {
    Write-Host "[2/4] Chrome Extension, Token and Tier are ALREADY ready." -ForegroundColor Green
} else {
    # Auto-detect profile with Flowboard extension installed
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
        # Launch Chrome with both localhost:5173 and Google Flow tabs in target profile
        Start-Process "chrome.exe" -ArgumentList "--profile-directory=`"$targetProfile`" --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding http://localhost:5173/ https://labs.google/fx/tools/flow"
    } catch {
        Write-Host "      [WARN] Could not launch chrome.exe directly: $_" -ForegroundColor Red
    }
}

# --- 3. Wait for Extension + Token + Paygate Tier (Active Poll Loop) ---
Write-Host "[3/4] Checking Chrome Extension, Token and Tier status..." -ForegroundColor Yellow
$ready = $false
$maxAttempts = 45  # 90 seconds total (45 * 2s) — accounts for Chrome startup + extension init

# Quick pre-flight: if the system is already fully ready (e.g. from a
# previous run), skip the loop entirely. This avoids a pointless 90s wait
# when Chrome was already open with the extension connected.
try {
    $pf = Invoke-RestMethod -Uri $agentHealthUrl -TimeoutSec 2 -ErrorAction SilentlyContinue
    $pfKey = $false
    if ($pf.ws_stats) { $pfKey = [bool]$pf.ws_stats.flow_key_present }
    if ($pf.extension_connected -and $pfKey) {
        $pfMe = Invoke-RestMethod -Uri "http://127.0.0.1:8101/api/auth/me" -TimeoutSec 3 -ErrorAction SilentlyContinue
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
        # Trigger scan nudge to request extension token/userinfo replay
        try {
            Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8101/api/auth/scan" -TimeoutSec 3 -ErrorAction SilentlyContinue | Out-Null
        } catch {}

        # Mid-check: if we're past attempt 20 and tier is still None,
        # force a recapture to get a fresh token from the Flow tab.
        if ($attempt -eq 20) {
            Write-Host "      [RETRY] Attempting force_recapture for fresh token..." -ForegroundColor DarkYellow
            try {
                Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8101/api/auth/scan" -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null
            } catch {}
        }

        $health = Invoke-RestMethod -Uri $agentHealthUrl -TimeoutSec 2 -ErrorAction SilentlyContinue
        $hasKey = $false
        if ($health.ws_stats) {
            $hasKey = [bool]$health.ws_stats.flow_key_present
        }
        $extConn = [bool]$health.extension_connected

        # Also check paygate tier
        $hasTier = $false
        if ($extConn -and $hasKey) {
            try {
                $me = Invoke-RestMethod -Uri "http://127.0.0.1:8101/api/auth/me" -TimeoutSec 3 -ErrorAction SilentlyContinue
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
    # Print a diagnostic summary showing exactly which check failed
    Write-Host ""
    Write-Host "      -------------------------------------------------------------" -ForegroundColor Red
    Write-Host "      READINESS CHECK FAILED after $($maxAttempts * 2) seconds" -ForegroundColor Red
    Write-Host "" -ForegroundColor Red

    # Re-check each stage individually for the diagnostic
    $diagExt = $false; $diagKey = $false; $diagTier = $false
    try {
        $dh = Invoke-RestMethod -Uri $agentHealthUrl -TimeoutSec 2 -ErrorAction SilentlyContinue
        $diagExt = [bool]$dh.extension_connected
        if ($dh.ws_stats) { $diagKey = [bool]$dh.ws_stats.flow_key_present }
        if ($diagExt -and $diagKey) {
            $dm = Invoke-RestMethod -Uri "http://127.0.0.1:8101/api/auth/me" -TimeoutSec 3 -ErrorAction SilentlyContinue
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

# --- 4. Execute Automated Generation ---
if ($VerifyOnly) {
    Write-Host ""
    Write-Host "[4/4] VERIFY ONLY MODE - System is READY for video generation!" -ForegroundColor Green
    Write-Host "      Run without -VerifyOnly to start generating." -ForegroundColor Gray
    exit 0
}

Write-Host "[4/4] Starting Video Generation Job..." -ForegroundColor Cyan
Write-Host ""

$automateScript = Join-Path $RepoRoot "automate_one.ps1"
& $automateScript -PromptsFile $PromptsFile
