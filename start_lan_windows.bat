@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup_windows.bat first.& pause & exit /b 1)
echo.
echo SRS LAN DEMO: allows another phone on the SAME Wi-Fi to scan the station QR.
echo Find this computer's IPv4 address below (for example 192.168.1.20).
ipconfig | findstr /i "IPv4"
echo.
echo Set the QR base address under Operator - Station QR Code to:
echo    http://YOUR-COMPUTER-IPv4:8000
echo Windows Firewall may request permission; allow only trusted private networks.
echo Never expose this demo server directly to the public internet.
echo.
set SRS_HOST=0.0.0.0
.venv\Scripts\python.exe run.py
pause
