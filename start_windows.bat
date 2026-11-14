@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup_windows.bat first.& pause & exit /b 1)
echo Open this address in your browser: http://127.0.0.1:8000
.venv\Scripts\python.exe run.py
pause
