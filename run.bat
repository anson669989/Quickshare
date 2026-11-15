@echo off
rem 以專案的虛擬環境啟動 Quick Share
cd /d "%~dp0"
.venv\Scripts\python.exe run.py
pause
