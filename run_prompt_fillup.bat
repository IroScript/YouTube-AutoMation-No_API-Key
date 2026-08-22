@echo off
title Autonomous Prompt Fillup Loop Engine (Part 1)
cd /d "%~dp0"
echo ======================================================================
echo           AUTONOMOUS PROMPT FILLUP LOOP ENGINE (PART 1)
echo ======================================================================
echo.
echo Running continuous backward dependency loop (Fresh Chrome per cycle)...
echo Press Ctrl+C at any time to stop gracefully.
echo.

set PYTHONUNBUFFERED=1

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -u run_prompt_fillup.py %*
) else (
    python -u run_prompt_fillup.py %*
)

echo.
pause

