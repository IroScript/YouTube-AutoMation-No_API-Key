@echo off
title Video Pipeline Runner (Part 2: 1Video10Sec Packaging)
cd /d "%~dp0"
echo ======================================================================
echo           VIDEO PIPELINE RUNNER (PART 2: 1VIDEO10SEC PACKAGING)
echo ======================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_video_pipeline.py %*
) else (
    python run_video_pipeline.py %*
)

echo.
pause
