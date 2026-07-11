@echo off
REM ============================================================================
REM Flowboard — One-click stopper
REM Closes the Agent + Frontend Terminal windows started by start_flowboard.bat
REM ============================================================================

setlocal

echo.
echo ============================================================
echo  Flowboard Stopper
echo ============================================================
echo  [1/3] Closing "Flowboard Agent (:8101)" window...
echo  [2/3] Closing "Flowboard Frontend (:5173)" window...
echo ============================================================
echo.

REM ─── 1. Close the Agent Terminal window by title ──────────────────────────
taskkill /FI "WINDOWTITLE eq Flowboard Agent (:8101)*" /F /T 2>nul
if %ERRORLEVEL%==0 (
    echo  [OK] Agent window closed.
) else (
    echo  [INFO] Agent window was not running or already closed.
)

REM ─── 2. Close the Frontend Terminal window by title ───────────────────────
taskkill /FI "WINDOWTITLE eq Flowboard Frontend (:5173)*" /F /T 2>nul
if %ERRORLEVEL%==0 (
    echo  [OK] Frontend window closed.
) else (
    echo  [INFO] Frontend window was not running or already closed.
)

REM ─── 3. Belt-and-suspenders: kill any leftover processes on our ports ─────
echo.
echo  [3/3] Killing leftover processes on ports 8101 / 9223 / 5173-5175...
for %%P in (8101 9223 5173 5174 5175) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
        taskkill /F /PID %%A /T 2>nul >nul
    )
)

REM Also kill any orphaned uvicorn.exe or node.exe specifically tied to flowboard
taskkill /F /IM uvicorn.exe /T 2>nul >nul

echo.
echo ============================================================
echo  Flowboard stopped.
echo ============================================================
echo.

endlocal