@echo off
REM ============================================================================
REM Flowboard — One-click launcher
REM Starts Agent (port 8101) + Frontend (port 5173) in separate Terminal windows.
REM ============================================================================

setlocal

REM Paths
set "ROOT=%~dp0"
set "AGENT_DIR=%ROOT%flowboard\agent"
set "FRONTEND_DIR=%ROOT%flowboard\frontend"

REM Verify folders exist
if not exist "%AGENT_DIR%\.venv\Scripts\python.exe" (
    echo [ERROR] Agent venv not found at: %AGENT_DIR%\.venv\Scripts\python.exe
    echo Please reinstall Python or recreate the venv. See FLOWBOARD_GUIDE.md
    pause
    exit /b 1
)
if not exist "%FRONTEND_DIR%\package.json" (
    echo [ERROR] Frontend package.json not found at: %FRONTEND_DIR%\package.json
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Flowboard Launcher
echo ============================================================
echo  [1/4] Starting Agent (FastAPI on :8101)...
echo  [2/4] Starting Frontend (Vite on :5173)...
echo ============================================================
echo.

REM ─── 1. Start Agent in its own Terminal window ─────────────────────────────
start "Flowboard Agent (:8101)" cmd /k ^
    "cd /d "%AGENT_DIR%" && .venv\Scripts\python.exe -m uvicorn flowboard.main:app --port 8101 --timeout-graceful-shutdown 2"

REM ─── 2. Wait for Agent port to come up ─────────────────────────────────────
echo  [3/4] Waiting for Agent health check (http://127.0.0.1:8101/api/health)...
set /a ATTEMPTS=0
:WAIT_AGENT
set /a ATTEMPTS+=1
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 -Uri 'http://127.0.0.1:8101/api/health').StatusCode } catch { 0 }" > "%TEMP%\flowboard_agent_status.txt" 2>nul
set /p AGENT_STATUS=<"%TEMP%\flowboard_agent_status.txt"
if "%AGENT_STATUS%"=="200" goto AGENT_OK
if %ATTEMPTS% GEQ 30 (
    echo  [ERROR] Agent did not start within 30 seconds.
    echo  Check the "Flowboard Agent (:8101)" window for errors.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto WAIT_AGENT
:AGENT_OK
echo  [OK] Agent is up.

REM ─── 3. Start Frontend in its own Terminal window ─────────────────────────
start "Flowboard Frontend (:5173)" cmd /k ^
    "cd /d "%FRONTEND_DIR%" && npm run dev"

REM ─── 4. Wait for Frontend port to come up ──────────────────────────────────
echo  [4/4] Waiting for Frontend (http://localhost:5173)...
set /a ATTEMPTS=0
:WAIT_FRONTEND
set /a ATTEMPTS+=1
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 -Uri 'http://localhost:5173/').StatusCode } catch { 0 }" > "%TEMP%\flowboard_fe_status.txt" 2>nul
set /p FE_STATUS=<"%TEMP%\flowboard_fe_status.txt"
if "%FE_STATUS%"=="200" goto FRONTEND_OK
if %ATTEMPTS% GEQ 30 (
    echo  [WARN] Frontend did not respond within 30 seconds.
    echo  Vite may still be compiling. Check "Flowboard Frontend (:5173)" window.
    goto FRONTEND_DONE
)
timeout /t 1 /nobreak >nul
goto WAIT_FRONTEND
:FRONTEND_OK
echo  [OK] Frontend is up.
:FRONTEND_DONE

REM ─── Cleanup status files ─────────────────────────────────────────────────
del "%TEMP%\flowboard_agent_status.txt" 2>nul
del "%TEMP%\flowboard_fe_status.txt" 2>nul

echo.
echo ============================================================
echo  Flowboard is running.
echo ============================================================
echo  Agent    : http://127.0.0.1:8101
echo  Frontend : http://localhost:5173  (open this in your browser)
echo  WebSocket: ws://127.0.0.1:9223  (extension auto-connects)
echo.
echo  Tip: Chrome extension must already be loaded via chrome://extensions/.
echo       See FLOWBOARD_GUIDE.md for first-time setup.
echo.
echo  To stop both servers: double-click stop_flowboard.bat
echo ============================================================
echo.

endlocal