@echo off
REM ============================================================================
REM Flowboard Bridge — Chrome extension installer
REM
REM Opens chrome://extensions directly on the right Chrome profile (Profile 6
REM by default — edit CHROME_PROFILE_DIR below to switch). You then click
REM "Load unpacked" once and select the extension folder.
REM
REM Why this approach (and not "just open chrome://..."):
REM   * `start chrome://extensions` from a .bat doesn't reliably bind to
REM     Chrome on Windows 11 — it can fall back to MS Store ("you'll need
REM     a new app to open this...") if the chrome:// protocol isn't
REM     registered for the current user. We invoke chrome.exe directly,
REM     so Chrome always opens.
REM   * Chrome 137+ (stable) refuses --load-extension from a normal launch
REM     — it's a security hardening that landed alongside Manifest V3.
REM     Only "Load unpacked" via the extensions UI works on stable. So
REM     we land you on that page directly with Dev Mode already enabled.
REM
REM Why we pre-enable Dev Mode in Preferences.json:
REM   Without Dev Mode the "Load unpacked" button is hidden. We force
REM   it on via force_dev_mode.ps1 so the button is ready the moment
REM   the page loads — no toggle round-trip.
REM
REM Profile: defaults to "Profile 6" because that's where Chrome created
REM          the unpacked-extensions folder when the user tried to load
REM          Flowboard Bridge earlier. If you'd rather use Default, edit
REM          CHROME_PROFILE_DIR.
REM ============================================================================

setlocal EnableExtensions

REM ─── Config ────────────────────────────────────────────────────────────────
set "CHROME_PROFILE_DIR=Profile 6"
set "CHROME_USER_DATA_DIR=%LOCALAPPDATA%\Google\Chrome\User Data"

set "CHROME_CANDIDATE_1=C:\Program Files\Google\Chrome\Application\chrome.exe"
set "CHROME_CANDIDATE_2=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
set "CHROME_CANDIDATE_3=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

set "ROOT=%~dp0"
set "EXT_DIR=%ROOT%flowboard\extension"

echo.
echo ============================================================
echo  Flowboard Bridge — Chrome extension installer
echo ============================================================

REM ─── Sanity checks ─────────────────────────────────────────────────────────
if not exist "%EXT_DIR%\manifest.json" (
    echo [ERROR] Extension folder not found:
    echo         %EXT_DIR%
    echo         Make sure you ran this from the repo root.
    pause
    exit /b 1
)

set "CHROME_EXE="
if exist "%CHROME_CANDIDATE_1%" set "CHROME_EXE=%CHROME_CANDIDATE_1%"
if not defined CHROME_EXE if exist "%CHROME_CANDIDATE_2%" set "CHROME_EXE=%CHROME_CANDIDATE_2%"
if not defined CHROME_EXE if exist "%CHROME_CANDIDATE_3%" set "CHROME_EXE=%CHROME_CANDIDATE_3%"

if not defined CHROME_EXE (
    echo [ERROR] Could not find chrome.exe in any standard location.
    echo         Install Chrome from https://google.com/chrome and retry.
    pause
    exit /b 1
)

if not exist "%CHROME_USER_DATA_DIR%\%CHROME_PROFILE_DIR%" (
    echo [WARN] Profile folder does not exist: %CHROME_PROFILE_DIR%
    echo        Falling back to Default.
    set "CHROME_PROFILE_DIR=Default"
)

echo  Chrome    : %CHROME_EXE%
echo  Profile   : %CHROME_PROFILE_DIR%
echo  Extension : %EXT_DIR%
echo ============================================================
echo.

REM ─── Pre-flight: flip Dev Mode = true in Preferences.json ──────────────────
REM Without Dev Mode, the "Load unpacked" button is hidden in
REM chrome://extensions. We toggle it via the JSON file directly so the
REM button is ready by the time the page finishes loading.
echo  [1/3] Enabling Developer Mode in %CHROME_PROFILE_DIR%...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%force_dev_mode.ps1" %CHROME_PROFILE_DIR%
if errorlevel 1 (
    echo         [WARN] Could not toggle Dev Mode automatically.
    echo                You'll need to flip the toggle manually below.
)
echo.

REM ─── Open chrome://extensions in the chosen profile ─────────────────────────
REM Direct chrome.exe invocation — bypasses MS Store protocol-handler race.
REM The page lands with Dev Mode ON, so "Load unpacked" is visible.
echo  [2/3] Opening chrome://extensions in %CHROME_PROFILE_DIR%...
start "" "%CHROME_EXE%" ^
    --user-data-dir="%CHROME_USER_DATA_DIR%\%CHROME_PROFILE_DIR%" ^
    --profile-directory="%CHROME_PROFILE_DIR%" ^
    --no-first-run ^
    --no-default-browser-check ^
    "chrome://extensions/?id=flowboard-bridge"

echo.
echo ============================================================
echo  [3/3] Final 30-second manual step
echo ============================================================
echo.
echo  A Chrome window is now open at chrome://extensions.
echo  Confirm "Developer mode" is ON (top-right toggle).
echo.
echo  Then:
echo    1. Click "Load unpacked" (top-left of the page)
echo    2. In the file picker, navigate to and select this folder:
echo.
echo           %EXT_DIR%
echo.
echo    3. A card titled "Flowboard Bridge" should appear with
echo       version 0.0.5 and NO red "Errors" button.
echo.
echo  Then open https://labs.google/fx/tools/flow — the extension
echo  will auto-connect to the Flowboard Agent over ws://127.0.0.1:9223.
echo.
echo  Restart the Agent if it isn't running:
echo     start_flowboard.bat
echo ============================================================
echo.

endlocal