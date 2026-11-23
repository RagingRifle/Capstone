@echo off
title EdgeCare AI Simulator Launcher
echo ============================================================
echo   Starting EdgeCare AI - Adaptive Edge-Cloud Simulator
echo ============================================================
cd /d "D:\Projects\Capstone"

:: Open default web browser automatically after 2 seconds
start "" timeout /t 2 >nul & start http://localhost:8050

:: Start python server
".\venv\Scripts\python.exe" dashboard\app.py

pause
