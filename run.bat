@echo off
REM Double-click on Windows: installs requirements (first time) and starts PartCheck.
cd /d "%~dp0"
python -c "import cv2, flask, numpy" 2>nul || pip install -r requirements.txt
start "" /b cmd /c "timeout /t 3 >/dev/null & start http://127.0.0.1:8765"
python app.py
pause
