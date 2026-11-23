@echo off
cd /d "%~dp0"
python tools\opennbt_gui.py
if errorlevel 1 pause
