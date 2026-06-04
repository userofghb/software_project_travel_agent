@echo off
cd /d "%~dp0backend"
python -m uvicorn app.main:app --reload --port 8000 >> "%~dp0backend-server.out.log" 2>> "%~dp0backend-server.err.log"
