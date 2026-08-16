@echo off
title Flowboard Single-Click Video Generator
echo ============================================================
echo  FLOWBOARD SINGLE-CLICK AUTONOMOUS VIDEO GENERATOR
echo ============================================================
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0run_single_click_automation.ps1"
pause
