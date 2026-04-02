@echo off
echo Starting Ростелеком Smart Home Backend...
cd /d "%~dp0backend"
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
pause
