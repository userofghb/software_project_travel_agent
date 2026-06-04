@echo off
cd /d "%~dp0frontend"
npm.cmd run dev -- --host 127.0.0.1 >> "%~dp0frontend-server.out.log" 2>> "%~dp0frontend-server.err.log"
