@echo off
rem Gibt Jahresring fuer Handys und weitere PCs im eigenen Netzwerk frei und prueft die Einstellungen.
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Es werden Administratorrechte gebraucht - bitte die folgende Frage mit "Ja" beantworten.
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Handy-Freigabe.ps1"
pause
