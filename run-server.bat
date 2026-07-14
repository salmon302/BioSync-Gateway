@echo off
cd /d "%~dp0\middleware"
"C:\Program Files\Python310\python.exe" -m uvicorn api.main:app --host localhost --port 8000 --reload
pause
