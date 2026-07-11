@echo off
REM ============================================================================
REM Flowboard — One-click stopper (robust)
REM
REM Stops both Agent (FastAPI on :8101 + WebSocket on :9223) and Frontend
REM (Vite on :5173-5175). Uses PowerShell for reliable process discovery
REM because:
REM   - netstat parsing varies across Windows versions / IPv4 vs IPv6 bind
REM   - window-title-based kill misses instances started outside this script
REM     (e.g. agent that survived a session break, or via `start /B`)
REM   - tree-kill ensures children are taken down too — orphan node
REM     processes were the original complaint
REM
REM Idempotent: safe to run multiple times. Reports what was killed and
REM what was already gone.
REM ============================================================================

setlocal

REM ─── Elevation check ──────────────────────────────────────────────────────
REM Flowboard's Agent (uvicorn.exe) and Frontend (node.exe) often run from
REM a session that has admin rights (e.g. when started from an elevated
REM PowerShell, or by an IDE like VS Code running as admin). Plain
REM Stop-Process / taskkill /F cannot terminate admin-owned processes
REM without elevation — silent failure.
REM
REM Detect: if `net session` errors out, we're not admin. In that case,
REM re-launch this same script with `Start-Process -Verb RunAs`, which
REM shows the standard UAC consent prompt. After the elevated instance
REM does its job, we exit (this non-elevated copy does nothing more).
net session >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Not running as Administrator - relaunching with elevation...
    echo.
    powershell -NoProfile -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', '\"%~f0\"' -Verb RunAs"
    exit /b 0
)

echo.
echo ============================================================
echo  Flowboard Stopper (robust)
echo ============================================================
echo  Scanning ports: 8101 (agent) 9223 (agent WS) 5173-5176 (frontend)
echo ============================================================
echo.

REM ─── Step 1: Try window-title kill (clean shutdown for live sessions) ────
echo  [1/4] Closing Flowboard Terminal windows by title (if any)...

set "AGENT_TITLE_OK="
taskkill /FI "WINDOWTITLE eq Flowboard Agent (:8101)*" /F /T 2>nul
if %ERRORLEVEL%==0 set "AGENT_TITLE_OK=closed" & echo         - Agent window closed.

taskkill /FI "WINDOWTITLE eq Flowboard Frontend (:5173)*" /F /T 2>nul
if %ERRORLEVEL%==0 echo         - Frontend window closed.

if not defined AGENT_TITLE_OK (
    echo         - No live Flowboard Terminal windows found.
)

echo.

REM ─── Step 2: Port-based kill via PowerShell (handles IPv4 + IPv6) ────────
echo  [2/4] Killing listeners on Flowboard ports...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ports = 8101,9223,5173,5174,5175,5176;" ^
    "$killed = 0;" ^
    "foreach ($p in $ports) {" ^
    "  $conns = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue;" ^
    "  if ($conns) {" ^
    "    foreach ($c in $conns) {" ^
    "      $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue;" ^
    "      if ($proc) {" ^
    "        Write-Host ('         - Killing PID {0} ({1}) on port {2}' -f $proc.Id, $proc.ProcessName, $p);" ^
    "        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue;" ^
    "        $killed++" ^
    "      }" ^
    "    }" ^
    "  }" ^
    "}" ^
    "if ($killed -eq 0) { Write-Host '         - No leftover listeners found.' }" ^
    "else { Write-Host ('         - Total killed: {0}' -f $killed) }"

if errorlevel 1 (
    echo         [WARN] PowerShell port-kill failed. Try running as Administrator.
)

echo.

REM ─── Step 3: Belt-and-suspenders — kill orphaned flowboard processes ──────
echo  [3/4] Killing orphaned flowboard processes by name...

set "ORPHAN_KILLED=0"
for %%N in (uvicorn.exe) do (
    taskkill /F /IM %%N /T 2>nul >nul
    if not errorlevel 1 set /a ORPHAN_KILLED+=1
)

REM Walk all node.exe processes; if any was started from the flowboard
REM frontend folder (cwd or command line) it's ours — kill it. PowerShell
REM is the cleanest way to ask "what's this process's command line?".
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ourPaths = @('flowboard\frontend', 'flowboard\agent');" ^
    "$killed = 0;" ^
    "foreach ($p in Get-CimInstance Win32_Process -Filter \"Name = 'node.exe'\") {" ^
    "  foreach ($needle in $ourPaths) {" ^
    "    if ($p.CommandLine -and $p.CommandLine -like ('*' + $needle + '*')) {" ^
    "      Write-Host ('         - Killing PID {0} (node.exe in {1})' -f $p.ProcessId, $needle);" ^
    "      Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue;" ^
    "      $killed++; break" ^
    "    }" ^
    "  }" ^
    "}" ^
    "if ($killed -eq 0) { Write-Host '         - No orphaned node processes in flowboard paths.' }"

echo.

REM ─── Step 4: Final verification — re-scan ports ──────────────────────────
echo  [4/4] Final verification - re-scanning ports...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ports = 8101,9223,5173,5174,5175,5176;" ^
    "$stillListening = @();" ^
    "foreach ($p in $ports) {" ^
    "  $c = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue;" ^
    "  if ($c) { $stillListening += $p }" ^
    "}" ^
    "if ($stillListening.Count -eq 0) {" ^
    "  Write-Host '         - All Flowboard ports are free.' -ForegroundColor Green" ^
    "} else {" ^
    "  Write-Host ('         - STILL LISTENING on: ' + ($stillListening -join ', ')) -ForegroundColor Yellow" ^
    "  Write-Host '         - Wait 5s for TIME_WAIT sockets, then re-run this script.'" ^
    "}"

echo.
echo ============================================================
echo  Flowboard stopped.
echo ============================================================
echo.

endlocal