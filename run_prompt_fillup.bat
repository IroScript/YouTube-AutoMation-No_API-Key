@echo off
title Prompt Fillup Engine (Part 1)
cd /d "%~dp0"
echo ======================================================================
echo           PROMPT FILLUP ENGINE (PART 1: AUTONOMOUS HIERARCHY)
echo ======================================================================
echo.
echo Checking backward dependencies: categories -^> elements -^> ideas -^> prompts...
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_prompt_fillup.py %*
) else (
    python run_prompt_fillup.py %*
)

echo.
pause
