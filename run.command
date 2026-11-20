#!/bin/bash
# Double-click on macOS: installs requirements (first time) and starts PartCheck.
cd "$(dirname "$0")"
python3 -c "import cv2, flask, numpy" 2>/dev/null || pip3 install -r requirements.txt || pip3 install --user --break-system-packages -r requirements.txt
(sleep 2; open "http://127.0.0.1:8765") &
python3 app.py
