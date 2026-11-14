@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup_windows.bat first.& pause & exit /b 1)
echo Downloading licensed real product sample photographs from Wikimedia Commons...
.venv\Scripts\python.exe download_product_photos.py
pause
