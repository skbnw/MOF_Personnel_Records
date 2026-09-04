@echo off
cd /d "%~dp0.."
set ROOT=%CD%
"%ROOT%\venv\Scripts\python.exe" "%ROOT%\code\run_all.py"
