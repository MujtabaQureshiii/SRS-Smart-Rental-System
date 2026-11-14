@echo off
cd /d "%~dp0"
echo Smart Rental System - Windows Setup
where py >nul 2>&1
if %errorlevel%==0 (py -3 -m venv .venv) else (python -m venv .venv)
if errorlevel 1 (echo ERROR: Install Python 3.11+ and enable PATH.& pause & exit /b 1)
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (echo ERROR: Package installation failed. Check internet connection.& pause & exit /b 1)
echo.
echo Setup complete. Next: create_operator_windows.bat, then download_photos_windows.bat, then start_windows.bat.
pause
