@echo off
title Pipeline Progress & CSV Generator
cd /d "%~dp0"
echo ======================================================================
echo             PIPELINE PROGRESS & BLANK-VS-FILLED CSV GENERATOR
echo ======================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" generate_progress_csv.py %*
) else (
    python generate_progress_csv.py %*
)

echo.
pause
